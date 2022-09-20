import json
import sys
import os
import queue
import socket
import threading
import time
import torch
import psutil

HOME = os.path.expanduser("~")
SDPATH = os.path.join(HOME, "stablediffusion")
sys.path.append(f"{HOME}/Projects/ai/stablediffusion/stablediffusion")
SCRIPTS = {
    'txt2img': [
        ('prompt', ''),
        ('outdir', os.path.join(SDPATH, "txt2img")),
        ('skip_grid', ''),
        # ('skip_save', ''),
        ('ddim_steps', 50),
        ('plms', ''),
        # ('laion400m', ''),
        ('fixed_code', ''),
        ('ddim_eta', 0.0),
        ('n_iter', 1),
        ('H', 512),
        ('W', 512),
        ('C', 4),
        ('f', 8),
        ('n_samples', 1),
        ('n_rows', 0),
        ('scale', 7.5),
        # ('from-file', ''),
        ('config', os.path.join(SDPATH, 'configs/stable-diffusion/v1-inference.yaml')),
        ('ckpt', os.path.join(SDPATH, 'models/ldm/stable-diffusion-v1/model.ckpt')),
        ('seed', 42),
        ('precision', 'autocast'),
        ('do_nsfw_filter', ''),
        ('do_watermark', ''),
    ],
    'img2img': [
        ('prompt', ''),
        ('init_img', ''),
        ('outdir', os.path.join(SDPATH, "img2img")),
        ('skip_grid', True),
        ('skip_save', False),
        ('ddim_steps', 50),
        ('plms', ''),
        ('fixed_code', True),
        ('ddim_eta', 0.0),
        ('n_iter', 1),
        ('H', 512),
        ('W', 512),
        ('C', 4),
        ('f', 8),
        ('n_samples', 2),
        ('n_rows', 0),
        ('scale', 5.0),
        ('strength', 0.75),
        ('from-file', ''),
        ('config', os.path.join(SDPATH, 'configs/stable-diffusion/v1-inference.yaml')),
        ('ckpt', os.path.join(SDPATH, 'models/ldm/stable-diffusion-v1/model.ckpt')),
        ('seed', 42),
        ('precision', 'autocast'),
        ('do_nsfw_filter', ''),
        ('do_watermark', ''),
    ],
    'inpaint': [
        ('indir', f'{HOME}/inpaint/input'),
        ('outdir', f'{HOME}/inpaint'),
        ('steps', 50),
    ],
    'knn2img': [
        ('prompt', ''),
        ('outdir', f'{HOME}/knn2img'),
        ('skip_grid', True),
        ('ddim_steps', 50),
        ('n_repeat', 1),
        ('plms', True),
        ('ddim_eta', 0.0),
        ('n_iter', 1),
        ('H', 768),
        ('W', 768),
        ('n_samples', 1),
        ('n_rows', 0),
        ('scale', 5.0),
        ('from-file', ''),
        ('config', os.path.join(SDPATH, 'configs/retrieval-augmented-diffusion/768x768.yaml')),
        ('ckpt', os.path.join(SDPATH, 'models/rdm/rdm768x768/model.ckpt')),
        ('clip_type', 'ViT-L/14'),
        ('database', 'artbench-surrealism'),
        ('use_neighbors', False),
        ('knn', 10),
    ],
    'train_searcher': [
        ('d', 'stablediffusion/data/rdm/retrieval_database/openimages'),
        ('target_path', 'stablediffusion/data/rdm/searchers/openimages'),
        ('knn', 20),
    ],
}



class StableDiffusionRunner:
    stablediffusion = None
    model = None
    device = None

    def connect(self):
        pass

    def start(self):
        pass

    def process_data_value(self, key, value):
        """
        Process the data value. Ensure that we use the correct types.
        :param key: key
        :param value: value
        :return: processed value
        """
        if value == "true":
            return True
        if value == "false":
            return False
        if key in [
            "ddim_steps", "n_iter", "H", "W", "C", "f",
            "n_samples", "n_rows", "seed"
        ]:
            return int(value)
        if key in ["ddim_eta", "scale", "strength"]:
            return float(value)
        return value

    def process_options(self, options, data):
        # get all keys from data
        keys = data.keys()
        for index, opt in enumerate(options):
            if opt[0] in keys:
                options[index] = (
                    opt[0],
                    self.process_data_value(
                        opt[0],
                        data.get(opt[0], opt[1])
                    )
                )
        return options

    def txt2img_sample(self, data):
        print("Sampling txt2img")
        return self._txt2img_loader.sample(
            options=self.process_options(self.txt2img_options, data)
        )

    def img2img_sample(self, data):
        return self._img2img_loader.sample(
            options=self.process_options(self.img2img_options, data)
        )

    def __init__(self, *args, **kwargs):
        self.txt2img_options = kwargs.get("txt2img_options", None)
        self.img2img_options = kwargs.get("img2img_options", None)
        if self.txt2img_options is None:
            raise Exception("txt2img_options is required")
        if self.img2img_options is None:
            raise Exception("img2img_options is required")

        from classes.txt2img import Txt2Img
        from classes.img2img import Img2Img

        # start a txt2img loader instance
        self._txt2img_loader = Txt2Img(
            options=self.txt2img_options,
            model=self.model,
            device=self.device
        )
        # initialize img2img loader and pass it the same model and device
        self._img2img_loader = Img2Img(
            options=self.img2img_options,
            model=self._txt2img_loader.model,
            device=self._txt2img_loader.device
        )


class Connection:
    """
    Connects to Stable Diffusion service
    """

    threads = []
    pid = None  # keep track of krita process id

    @property
    def name(self):
        return self.__str__()

    def __str__(self):
        return "Connection"

    def start_thread(self, target, daemon=False, name=None):
        t = threading.Thread(target=target, daemon=daemon)
        if name:
            t.setName(name)
        t.start()
        self.threads.append(t)
        return t

    def connect(self):
        """
        Override this method to set up a connection to something.

        Do not call connect directly, it should be used in a thread.

        Use the start() method which starts this method in a new thread.
        :return: None
        """
        pass

    def disconnect(self):
        """
        Override this method to disconnect from something.
        :return: None
        """
        pass

    def reconnect(self):
        """
        Disconnects then reconnects to service. Does not stop the thread.
        :return: None
        """
        self.disconnect()
        self.connect()

    def start(self):
        """
        Starts a new thread with a connection to service.
        :return: None
        """
        self.start_thread(
            target=self.connect,
            name="Connection thread"
        )

    def stop(self):
        """
        Disconnects from service and stops the thread
        :return: None
        """
        self.disconnect()
        print("Stopping connection thread...")
        for n in range(len(self.threads)):
            thread = self.threads[n]
            print(f"{n+1} of {len(self.threads)} Stopping thread {thread.getName()} from {self.name}...")
            thread.join()
            print(f"Stopped thread {thread.getName()}...")
        print("All threads stopped")

    def restart(self):
        """
        Stops the thread and starts a new one which in turn stops and starts
        connection to service.
        :return: None
        """
        self.stop()
        self.start()

    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs
        self.start()


class SocketConnection(Connection):
    """
    Opens a socket on a server and port.

    parameters:
    :host: Hostname or IP address of the service
    :port: Port of the service
    """
    port = 50006
    host = "localhost"
    soc = None
    soc_connection = None
    soc_addr = None

    def __str__(self):
        return "SocketConnection"

    def open_socket(self):
        """
        Open a socket conenction
        :return:
        """

    def handle_open_socket(self):
        """
        Override this method to handle open socket
        :return:
        """
        pass

    def connect(self):
        self.open_socket()
        self.handle_open_socket()

    def disconnect(self):
        if self.soc_connection:
            self.soc_connection.close()

    def __init__(self, *args, **kwargs):
        self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.soc.settimeout(1)
        super().__init__(*args, **kwargs)


class SocketServer(SocketConnection):
    max_client_connections = 1
    quit_event = None

    def __str__(self):
        return "SocketServer"

    @property
    def has_connection(self):
        return self.soc_connection is not None

    def callback(self, msg):
        """
        Override this method or pass it in as a parameter to handle messages
        :param msg:
        :return:
        """
        pass

    def worker(self):
        """
        Worker is started in a thread and waits for messages that are appended
        to the queue. When a message is received, it is passed to the callback
        method. The callback method should be overridden to handle the message.
        :return:
        """
        pass

    def open_socket(self):
        try:
            self.soc.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.soc.bind((self.host, self.port))
        except socket.error as err:
            print(f"Failed to open a socket at {self.host}:{self.port}")
            print(str(err))
        print(f"Socket opened {self.soc}")

    def try_quit(self):
        has_krita_process = False
        for proc in psutil.process_iter():
            if int(proc.pid) == int(self.pid):
                has_krita_process = True
                break
        if not has_krita_process:
            print("krita process not found, quitting")
            self.quit_event.set()
            self.response_queue.put("quit")
        return self.quit_event.is_set()

    def handle_open_socket(self):
        """
        Listen for incoming connections.
        Returns:
        """
        print("Opening socket...")
        self.soc.listen(self.max_client_connections)
        print("Socket opened")
        while True:
            print("Waiting for a connection")
            self.soc.settimeout(1)
            try:
                self.soc_connection, self.soc_addr = self.soc.accept() if not self.quit_event.is_set() else (None, None)
            except socket.timeout:
                pass
            if self.soc_connection:
                print(f"Connection established with {self.soc_addr}")
                print("Awaiting message...")
            while True:
                if self.soc_connection:
                    try:
                        msg = self.soc_connection.recv(1024) if not self.quit_event.is_set() else None
                        if msg == b"pingping" or msg == b"ping":
                            # respond to ping
                            self.soc_connection.sendall(b"pong")
                            msg = None
                        if msg is not None and msg != b'':
                            print("Message received")
                            # push directly to queue
                            self.message = msg
                        if self.quit_event.is_set():
                            print("Quitting...")
                            # break from loop if we are quitting
                            break
                        time.sleep(1)
                    except ConnectionResetError:
                        break
                if self.quit_event.is_set(): break
            if self.quit_event.is_set(): break
            time.sleep(1)
        print("Socket server stopped")

    def watch_connection(self):
        while True:
            if self.try_quit():
                print("quitting connection")
                break
            time.sleep(1)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.quit_event = threading.Event()
        self.quit_event.clear()
        self.max_client_connections = kwargs.get(
            "max_client_connections",
            self.max_client_connections
        )
        t = self.start_thread(
            target=self.worker,
            name="socket server worker"
        )
        t.join()
        t = threading.Thread(
            target=self.watch_connection,
            name="watch connection"
        )
        t.start()
        t.join()


class SocketClient(SocketConnection):
    has_connection = False

    def __str__(self):
        return "SocketClient"

    def callback(self, msg):
        """
        Override this method or pass it in as a parameter to handle messages
        :param msg:
        :return:
        """
        pass

    def worker(self):
        """
        Worker is started in a thread and waits for messages that are appended
        to the queue. When a message is received, it is passed to the callback
        method. The callback method should be overridden to handle the message.
        :return:
        """
        pass

    def connect(self):
        print("Connecting to server...")
        while True:
            # check self.soc for connection
            if not self.has_connection:
                try:
                    self.soc.connect((self.host, self.port))
                    self.has_connection = True
                except Exception as e:
                    print("failed to connect", e)

            if self.quit_event.is_set():
                break

            if self.has_connection:
                try:
                    self.soc.sendall(b"ping")
                    response = self.soc.recv(1024)
                    if response != b'pong':
                        print("PUTTING RESPONSE INTO QUEUE")
                        self.queue.put(response)
                except Exception as e:
                    self.soc.close()
                    self.soc_connection = None
                    self.soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self.soc.settimeout(1)
            if self.quit_event.is_set(): break
            time.sleep(1)

    def __init__(self, *args, **kwargs):
        self.quit_event = threading.Event()
        self.quit_event.clear()
        self.queue = kwargs.get("queue", queue.SimpleQueue())
        super().__init__(*args, **kwargs)
        self.start_thread(
            target=self.worker,
            name="socket client worker"
        )
        self.start_thread(
            target=self.connect,
            name="socket client connect"
        )


class SimpleEnqueueSocketServer(SocketServer):
    """
    Creates a SimpleQueue and waits for messages to append to it.
    """
    def __str__(self):
        return "SimpleEnqueueSocketServer"

    @property
    def message(self):
        return ""

    @message.setter
    def message(self, msg):
        self.queue.put(msg)

    def worker(self):
        print("Simple enqueue server waiting for connection...")
        while self.quit_event.is_set():
            print("awaiting connection")
            if self.has_connection:     # if a client is connected...
                print("has connection")
                msg = self.queue.get()  # get a message from the queue
                try:                    # send to callback
                    self.callback(msg)
                except Exception as err:
                    print(f"Error in callback: {err}")
                    pass
            if self.quit_event.is_set(): break
            time.sleep(1)
        print("worker dead")

    def __init__(self, *args, **kwargs):
        self.do_run = True
        self.queue = kwargs.get("queue", queue.SimpleQueue())
        super().__init__(*args, **kwargs)


class SimpleEnqueueSocketClient(SocketClient):
    """
    Creates a SimpleQueue and waits for messages to append to it.
    """
    def __str__(self):
        return "SimpleEnqueueSocketClient"

    @property
    def message(self):
        return ""

    @message.setter
    def message(self, msg):
        self.queue.put(msg)

    def callback(self, message):
        self.soc.sendall(json.dumps(message).encode("utf-8"))

    def handle_response_default(self, msg):
        print("Pass handle_response to kwargs to override this method")

    def quit(self):
        self.quit_event.set()
        self.queue.put("quit")

    def worker(self):
        while not self.quit_event.is_set():
            print("Client waiting for message...")
            msg = self.queue.get()
            if msg == "quit":
                break
            print("Message received")
            try:
                msg = msg.decode("utf-8")
            except Exception as err:
                pass
            try:
                keys = msg.keys()
                self.callback(msg)
                continue
            except:
                pass
            if msg != "" and msg is not None:
                self.handle_response(msg)

    def __init__(self, *args, **kwargs):
        self.handle_response = kwargs.get("handle_response", self.handle_response_default)
        self.queue = kwargs.get("queue", queue.SimpleQueue())
        super().__init__(*args, **kwargs)


class StableDiffusionRequestQueueWorker(SimpleEnqueueSocketServer):
    def __str__(self):
        return "SimpleEnqueueSocketServer"

    def callback(self, data):
        """
        Handle a stable diffusion request message
        :return: None
        """
        print("SERVER CALLBACK")
        data = json.loads(data.decode("utf-8"))
        response = None
        if data["type"] == "txt2img":
            response = self.sdrunner.txt2img_sample(data["options"])
        elif data["type"] == "img2img":
            response = self.sdrunner.img2img_sample(data["options"])
        if response is not None and response is not b'':
            self.response_queue.put(response)


    def response_queue_worker(self):
        while True:
            print("response queue worker")
            response = self.response_queue.get()
            print(response)
            if response == "quit":
                break
            res = json.dumps(response)
            if res is not None and res is not b'':
                print("SENDING RESPONSE")
                try:
                    self.soc_connection.sendall(res.encode("utf-8"))
                except Exception as e:
                    print("Failed to send response", e)
            if self.quit_event.is_set(): break
            time.sleep(1)

    def init_sd_runner(self):
        print("Starting Stable Diffusion Runner...")
        self.sdrunner = StableDiffusionRunner(
            txt2img_options=SCRIPTS["txt2img"],
            img2img_options=SCRIPTS["img2img"]
        )
        torch.cuda.empty_cache()
        print("*"* 80)
        print("*" * 80)
        print("*" * 80)
        print("*" * 80)
        print("SD Runner started")
        print("*" * 80)
        print("*" * 80)
        print("*" * 80)
        print("*" * 80)

    def __init__(self, *args, **kwargs):
        self.pid = kwargs.get("pid")
        # create a stable diffusion runner service
        self.response_queue = kwargs.get("response_queue", queue.SimpleQueue())
        if not self.response_queue:
            raise ValueError("response_queue is required")
        self.start_thread(
            target=self.response_queue_worker,
            name="response queue worker"
        )
        thread = self.start_thread(
            target=self.init_sd_runner,
            name="init stable diffusion runner"
        )
        thread.join()
        super().__init__(*args, **kwargs)
        self.stop()



class StableDiffusionResponseQueueWorker(SimpleEnqueueSocketServer):
    def __str__(self):
        return "StableDiffusionResponseQueueWorker"

    def callback(self, message):
        """
        Handle a stable diffusion response message
        :return: None
        """
        pass

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

