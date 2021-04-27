import threading
import logging
import time
import random
import yaml
from pathlib import Path
from flask import Flask, abort, Response, send_from_directory
from prometheus_client import Gauge, Counter, Summary, Histogram
from prometheus_client import generate_latest, CollectorRegistry

# Prometheus metrics generator inspired on https://github.com/little-angry-clouds/prometheus-data-generator

def read_configuration():
    path = "config.yml"
    config = yaml.safe_load(open(path))
    return config

class sfhserver:
    def __init__(self):
        """
        Initialize the flask endpoint and launch the function that will throw
        the threads that will update the metrics.
        """
        self.app = Flask(__name__)
        self.enable_webping()
        self.serve_metrics()
        self.init_metrics()

    def enable_webping(self):
        self.webping_status = "OK"
        return "Done"

    def disable_webping(self):
        self.webping_status = "Fail"
        return "Done"

    def get_webping_status(self):
        if self.webping_status == "Fail":
            return abort(Response('Fail', 404))
        return self.webping_status

    def init_metrics(self):
        """
        Launch the threads that will update the metrics.
        """
        self.threads = []
        self.registry = CollectorRegistry()
        self.data = read_configuration()
        for metric in self.data["config"]:
            if "labels" in metric:
                labels = metric["labels"]
            else:
                labels = []
            if metric["type"].lower() == "counter":
                instrument = Counter(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            elif metric["type"].lower() == "gauge":
                instrument = Gauge(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            elif metric["type"].lower() == "summary":
                instrument = Summary(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            elif metric["type"].lower() == "histogram":
                # TODO add support to overwrite buckets
                instrument = Histogram(
                    metric["name"],
                    metric["description"],
                    labels,
                    registry=self.registry
                )
            else:
                logging.warning(
                    "Unknown metric type {type} for metric {name}, ignoring.".format(**metric)
                )

            t = threading.Thread(
                target=self.update_metrics,
                args=(instrument, metric)
            )
            t.start()
            self.threads.append(t)

    def update_metrics(self, metric_object, metric_metadata):
        """
        Updates the metrics.
        Arguments:
        metric_object: a Prometheus initialized object. It can be a Gauge,
          Counter, Histogram or Summary.
        metric_metadata: the configuration related to the initialzed Prometheus
          object. It comes from the config.yml.
        """
        self.stopped = False
        while True:
            if self.stopped:
                break
            for sequence in metric_metadata["sequence"]:
                if self.stopped:
                    break

                if "labels" in sequence:
                    labels = [key for key in sequence["labels"].values()]
                else:
                    labels = []

                if "eval_time" in sequence:
                    timeout = time.time() + sequence["eval_time"]
                else:
                    logging.warning(
                        "eval_time for metric {} not set, setting default to 1.".format(metric_metadata["name"])
                    )
                    timeout = time.time() + 1


                logging.debug(
                    "Changing sequence in {} metric".format(metric_metadata["name"])
                )

                if "interval" in sequence:
                    interval = sequence["interval"]
                else:
                    logging.info(
                        "interval for metric {} not set, setting default to 1.".format(metric_metadata["name"])
                    )
                    interval = 1

                while True:
                    if self.stopped:
                        break
                    if time.time() > timeout:
                        break

                    if "value" in sequence:
                        value = sequence["value"]
                        if isinstance(value, float):
                            value = float(value)
                        else:
                            value = int(value)

                    elif "values" in sequence:
                        if "." in sequence["values"].split("-")[0]:
                            initial_value = float(sequence["values"].split("-")[0])
                            end_value = float(sequence["values"].split("-")[1])
                            value = random.uniform(initial_value, end_value)
                        else:
                            initial_value = int(sequence["values"].split("-")[0])
                            end_value = int(sequence["values"].split("-")[1])
                            value = random.randrange(initial_value, end_value)

                    if metric_metadata["type"].lower() == "gauge":
                        try:
                            operation = sequence["operation"].lower()
                        except:
                            logging.error(
                                "You must set an operation when using Gauge"
                            )
                            exit(1)
                        if operation == "inc":
                            if labels == []:
                                metric_object.inc(value)
                            else:
                                metric_object.labels(*labels).inc(value)
                        elif operation == "dec":
                            if labels == []:
                                metric_object.dec(value)
                            else:
                                metric_object.labels(*labels).dec(value)
                        elif operation == "set":
                            if labels == []:
                                metric_object.set(value)
                            else:
                                metric_object.labels(*labels).set(value)

                    elif metric_metadata["type"].lower() == "counter":
                        if labels == []:
                            metric_object.inc(value)
                        else:
                            metric_object.labels(*labels).inc(value)
                    elif metric_metadata["type"].lower() == "summary":
                        if labels == []:
                            metric_object.observe(value)
                        else:
                            metric_object.labels(*labels).observe(value)
                    elif metric_metadata["type"].lower() == "histogram":
                        if labels == []:
                            metric_object.observe(value)
                        else:
                            metric_object.labels(*labels).observe(value)
                    logging.debug(f"Sleep: {interval}")
                    time.sleep(interval)

    def serve_metrics(self):
        @self.app.route("/")
        def root():
            page = """
                    <html>
                    <h2>Simple Flask HTTP Server</h2>
                    <br>
                    >  <a href="/webping">/webping</a> - Get webping status.<br>
                    >  <a href="/webpingon">/webpingon</a> - Enable webping.<br>
                    >  <a href="/webpingoff">/webpingoff</a> - Disable webping.<br>
                    <br><h4>Prometheus Metrics Generator</h4>
                    >  <a href="/metrics">/metrics</a> - Get Prometheus Metrics.<br>
                    >  <a href="/metrics/reload">/metrics/reload</a> - Reload Prometheus Metrics.<br>
                    >  <a href="/metrics/configs">/metrics/configs</a> - Get Prometheus Metrics configs.<br>
                    </html>
                    """
            return page

        @self.app.route("/metrics/")
        def metrics():
            """
            Plain method to expose the prometheus metrics. Every time it's
            called it will recollect the metrics and generate the rendering.
            """
            metrics = generate_latest(self.registry)
            return Response(metrics,
                            mimetype="text/plain",
                            content_type="text/plain; charset=utf-8")

        @self.app.route("/metrics/reload")
        def reload():
            """
            Stops the threads and restarts them.
            """
            self.stopped = True
            for thread in self.threads:
                thread.join()
            self.init_metrics()
            logging.info("Configuration reloaded. Metrics will be restarted.")
            return Response("OK")

        @self.app.route("/metrics/configs")
        def configs():
            return self.data

        @self.app.route('/webping')
        def getwebping():
            return self.get_webping_status()

        @self.app.route('/webpingon')
        def webpingon():
            return self.enable_webping()

        @self.app.route('/webpingoff')
        def webpingoff():
            return self.disable_webping()

    def run_webserver(self):
        """
        Launch the flask webserver on a thread.
        """
        threading.Thread(
            target=self.app.run,
            kwargs={"port": "8080", "host": "0.0.0.0"}
        ).start()

if __name__ == "__main__":
    SERVER = sfhserver()
    SERVER.run_webserver()