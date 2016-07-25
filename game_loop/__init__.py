"""Reusable, extensible implementation of a multiprocess game loop."""

from time import time
from multiprocessing import Process, Queue
from logging import log
from Queue import Empty
import traceback


# render server commands
FRAME = "FRAME"
QUIT = "QUIT"

# render server responses
RUNNING = "RUNNING"
FRAME_REQ = "FRAME_REQ"
FATAL_ERROR = "FATAL_ERROR"


class RenderServerError (Exception):
    """Report an internal error in the render server."""
    pass


class RenderError (Exception):
    """Report a non-fatal error during rendering.

    Clients implementing render actions can use this exception to report an
    error condition that is only relevant for the current frame.
    """
    pass


class FatalRenderError (Exception):
    """Report a fatal error during rendering.

    Clients implementing render actions can use this exception to report an
    error condition that is terminal for the target rendering backend.  Raising
    this exception will cause the render server process to terminate.
    """
    pass


class RenderServer (object):
    """Responsible for launching and communicating with a render server process."""

    def __init__(self, render_action, report=False):
        """Create a new render server handle.

        Args:
            render_action: a closure to call to perform the frame render action.
                This function should accept three arguments:
                    - the absolute frame number
                    - the absolute time associated with the frame number
                    - the frame data
                This function may raise an exception if something goes wrong,
                    preferably either RenderError.  FatalRenderError or any other
                    exception will cause the render service to terminate.
                This function must be picklable.
            report (bool): have the render process print debugging information
        """
        self.render_action = render_action
        self.running = False
        self.command = None
        self.response = None
        self.server_proc = None
        self.report = report

    def start(self):
        """Launch an instance of the render server."""
        if not self.running:
            self.command = command = Queue()
            self.response = response = Queue()

            self.server_proc = server_proc = Process(
                target=run_render_server,
                args=(command, response, self.render_action, self.report))

            server_proc.start()
            # wait for server to succeed or fail
            resp, payload = response.get()

            if resp == FATAL_ERROR:
                raise Exception(payload[0], payload[1])
            elif resp == FRAME_REQ:
                # unclear how this happened.  kill the server and raise an error
                self._stop()
                raise Exception(
                    "Render server asked for a frame before reporting RUNNING.")
            elif resp != RUNNING:
                self._stop()
                raise Exception(
                    "Render server returned an unknown response: {}".format(resp))

            self.running = True

    def _stop(self):
        """Kill the server."""
        if self.command is not None:
            self.command.put((QUIT, None))
            self.command = None
            self.response = None
            if self.server_proc is not None:
                self.server_proc.join()
            self.running = False

    def stop(self):
        """Stop the server if it is running."""
        if self.running:
            self._stop()

    def pass_frame_if_ready(self, update_number, update_time, frame):
        """Pass the render server a frame if it is ready to draw one.

        Returns a boolean indicating if a frame was drawn or not.
        """
        if self.running:
            try:
                req, payload = self.response.get(block=False)
            except Empty:
                return False
            else:
                if req == FRAME_REQ:
                    self.command.put((FRAME, (update_number, update_time, frame)))
                    return True
                elif req == FATAL_ERROR:
                    self._stop()
                    raise RenderServerError(payload[0], payload[1])
                else:
                    raise RenderServerError(
                        "Unknown response: {}, {}".format(req, payload))
        return False

def run_render_server(command, response, render_action, report):
    """Run the frame drawing service.

    The control protocol for the server's command queue is as follows:
    (command, payload)
    Examples are
    (FRAME, (update_number, frame_time, frame)) -> data payload to draw a frame
    (QUIT, _) -> quit the server thread

    The server communicates with the control thread over the response queue.
    It requests a frame with
    (FRAME_REQ, _)
    and reports a fatal, thread-death error with
    (FATAL_ERROR, err)

    Args:
        command: the queue from which to draw commands
        response: the queue to respond on
        render_action: see RenderServer
    """
    try:
        # we're ready to render
        response.put((RUNNING, None))

        log_time = time()

        def log_error(err, kind, frame_number):
            log.error(
                "{} error during rendering of frame {}: {}"
                .format(kind, frame_number, err))

        while 1:
            # ready to draw a frame
            response.put((FRAME_REQ, None))

            # wait for a reply
            action, payload = command.get()

            # check if time to quit
            if action == QUIT:
                return
            # no other valid commands besides FRAME
            elif action != FRAME:
                # blow up with fatal error
                # we could try again, but who knows how we even got here
                raise RenderServerError("Unrecognized command: {}".format(action))

            frame_number, frame_time, frame = payload

            # render the payload we received
            try:
                render_action(frame_number, frame_time, frame)
            except RenderError as err:
                log_error(err, "Nonfatal", frame_number)
            except FatalRenderError as err:
                log_error(err, "Fatal", frame_number)
                raise

            if report:# and frame_number % 1 == 0:
                now = time()
                log.debug("Framerate: {}".format(1 / (now - log_time)))
                log_time = now

    except Exception as err:
        # some exception we didn't catch
        stacktrace = traceback.format_exc()
        response.put((FATAL_ERROR, (err, stacktrace)))
        return




