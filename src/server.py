from pathlib import Path
from flask import Flask, abort, Response, send_from_directory
app = Flask(__name__)

class webping():
    def __init__(self):
        self.enable_webping()

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


@app.route('/')
def main():
    return """
    <html>
    <h2>Simple Flask HTTP Server</h2>
    <br>
    >  /webping - Get webping status.<br>
    >  /webpingon - Enable webping.<br>
    >  /webpingoff - Disable webping.<br>
    </html>
    """

@app.route('/webping')
def getwebping():
    return webping.get_webping_status()

@app.route('/webpingon')
def webpingon():
    return webping.enable_webping()

@app.route('/webpingoff')
def webpingoff():
    return webping.disable_webping()

if __name__ == '__main__':
    webping = webping()
    app.debug = False
    app.run(host = '0.0.0.0',port=8080)