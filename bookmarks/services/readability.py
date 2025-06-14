import logging
import os
import signal
import subprocess

from django.conf import settings


class ReadabilityError(Exception):
    pass


logger = logging.getLogger(__name__)


def create_readable_html(url: str, snapshot_path: str, filepath: str):
    readability_script_path = './readable.js'

    # Set NODE_PATH to include global node_modules
    npm_global_path = subprocess.check_output(["npm", "root", "-g"]).decode().strip()
    env = os.environ.copy()
    env["NODE_PATH"] = npm_global_path

    # concat lists
    args = ['node', readability_script_path] + [url, snapshot_path, filepath]
    try:
        # Use start_new_session=True to create a new process group
        process = subprocess.Popen(args, env=env, start_new_session=True)
        process.wait(timeout=settings.LD_SINGLEFILE_TIMEOUT_SEC)

        # check if the file was created
        if not os.path.exists(filepath):
            raise ReadabilityError("Failed to create readable HTML")
    except subprocess.TimeoutExpired:
        # First try to terminate properly
        try:
            logger.error(
                "Timeout expired while creating readable html. Terminating process..."
            )
            process.terminate()
            process.wait(timeout=20)
            raise ReadabilityError("Timeout expired while creating readable html")
        except subprocess.TimeoutExpired:
            logger.error("Timeout expired while terminating. Killing process...")
            os.killpg(os.getpgid(process.pid), signal.SIGTERM)
            raise ReadabilityError("Timeout expired while creating readable html")
    except subprocess.CalledProcessError as error:
        raise ReadabilityError(f"Failed to create readable html: {error.stderr}")
