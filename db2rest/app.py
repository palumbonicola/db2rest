from werkzeug.wrappers import Request
import werkzeug.exceptions as ex
from werkzeug.wsgi import SharedDataMiddleware
from db2rest.db import DBAdapter
from db2rest.rest import RestAPI
from db2rest.exceptions import NotFound


class DB2Rest(object):

    def __init__(self, config, db_engine, host, port, log):
        self.url_map = create_map(db_engine)
        self.host = host
        self.port = port
        self.log = log
        self.db_adapter = DBAdapter(db_engine)

    def dispatch_request(self, request):
        adapter = self.url_map.bind_to_environ(request.environ)
        try:
            endpoint, values = adapter.match()
            api = RestAPI(self.db_adapter, values)
            values['view'] = endpoint
            return getattr(api, request.method.lower())(request, values)
        except ex.NotFound, e:
            return NotFound()
        except ex.HTTPException, e:
            return e

    def wsgi_app(self, environ, start_response):
        request = Request(environ)
        response = self.dispatch_request(request)
        return response(environ, start_response)

    def __call__(self, environ, start_response):
        return self.wsgi_app(environ, start_response)


def create_app(config_file):
    from sqlalchemy import create_engine
    import ConfigParser

    config = ConfigParser.ConfigParser()
    config.read(config_file)

    host = config.get('webserver', 'host')
    port = config.getint('webserver', 'port')
    db_engine = create_engine(config.get('db', 'string_connection'))
    log = create_logger(config.get('logger', 'level'))

    app = DB2Rest(config_file, db_engine, host, port, log)
    shared = SharedDataMiddleware(
        app.wsgi_app,
        {'/static':  os.path.join(os.path.dirname(__file__), 'static')})
    app.wsgi_app = shared
    return app


def create_logger(level):
    import logging
    logging.basicConfig(level=logging.getLevelName(level))
    return logging


def create_map(db_engine):
    from werkzeug.routing import Map, Rule
    from sqlalchemy.schema import MetaData
    meta = MetaData()
    meta.reflect(bind=db_engine)
    rules = [Rule('/', endpoint='Tables')]

    for table in reversed(meta.sorted_tables):
        rules.append(Rule("/%s" % table, endpoint='Table'))
    return Map(rules)


if __name__ == '__main__':
    import sys
    import os
    from werkzeug.serving import run_simple

    config_file = os.path.join(os.path.dirname(__file__), 'config.cfg')

    if len(sys.argv) > 1:
        config_file = sys.argv[1]

    app = create_app(config_file)

    run_simple(app.host, app.port, app, use_debugger=True, use_reloader=True)
