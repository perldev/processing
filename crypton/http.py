# -*- coding: utf-8 -*-
"""
    Collection of classes that we will use to override django
"""
import tornado.web
import threading
import logging
from main.api_http_common import caching

from django.contrib.sessions.models import Session
from django.conf import settings
from django.contrib.auth.models import User
# http request class synonym of django request
import Cookie
import sys, traceback

class MemCacheStore: 
    
    @staticmethod
    def key_function(key, keyprefix, version):
        return keyprefix+key
        
    def __init__(self, *args, **kwargs):
        logging.debug("setup memcache")
        self.keyprefix  = kwargs.get("keyprefix", "django.contrib.sessions.cache")
        
        self.storage = caching()
        self.is_local = False
        self.key_function = kwargs.get("key_function", lambda key: MemCacheStore.key_function(key, self.keyprefix, 0) )
    
    def get(self, key, default=None):
        return  self.storage.get( self.key_function(key) )


    def set(self, key, val):
         self.storage.set( self.key_function(key),  val )

    def delete(self, key):
       return  self.storage.delete( self.key_function(key) )
       

    def delete_many(self, list_of_keys):
        self.caches.delete_many([ self.key_function(key)  for key in list_of_keys])
    


class MemStore:
    _instance = None

    @classmethod
    def get_instance(cls):
        """
        Возвращает экземпляр ядра, если оно создано.
        :rtype : Core
        """
        if not cls._instance:
            raise RuntimeError('core is not created')
        return cls._instance

    @classmethod
    def is_created(cls):
        """
        Создано ли ядро?
        :rtype : bool
        """
        return cls._instance is not None

    @classmethod
    def create_instance(cls, *args, **kwargs):
        """
        Создаёт и возвращает объект ядра с настройками из объекта settings или из файла по settings_path.
        :rtype : Core
        """
        logging.debug('creating memstore instance')
        if kwargs.get("is_local", True):
            cls._instance = MemStore(*args, **kwargs)
        else:
            cls._instance = MemCacheStore(*args, **kwargs)
            
        logging.debug('memstore created: {0}'.format(cls._instance))
        return cls._instance

    def __init__(self, *args, **kwargs):
        self.storage = {}
        self.is_local = True

            
            

    def get(self, key, default=None):
        if self.storage.has_key(key):
            return self.storage[key]
        else:
            return default

    def get_storage(self):
        return self.storage

    def set_storage(self, storage):
        self.storage = storage
        return True

    def set(self, key, val):
        self.storage[key] = val

    def delete(self, key):
        if self.storage.has_key(key):
            del self.storage[key]
            return True
        else:
            return False

    def delete_many(self, list_of_keys):
        for i in list_of_keys:
            self.delete(i)


class HttpRequest:
    def __repr__(self):
        return "post : %s, get: %s, meta: %s, cookies: %s,  session: %s, user: %s" % (self.POST, self.GET, self.META, self.COOKIES, self.session, self.user)
        
    
    
    
    def __init__(self, *args, **kwargs):
        self.tornado_http_request = kwargs.get("request")
        request = self.tornado_http_request
        self.name = kwargs.get("name")
        self.method = request.method
        self.body = request.body
        self.GET = {}
        self.POST = {}
        self.REQUEST = {}
        self.META = request.headers
        self.COOKIES = request.cookies
        
        for key in request.query_arguments.keys():
            self.GET[key] = request.query_arguments[key]
            temp = self.GET[key]
            new_tmp = []
            for item in temp:
                new_tmp.append(item.decode())
            self.GET[key] = new_tmp

            if len(self.GET[key]) == 1:
                self.GET[key] = self.GET[key][0]

        for key in request.body_arguments.keys():
            self.POST[key] = request.body_arguments[key]
            temp = self.POST[key]
            new_tmp = []
            for item in temp:
                new_tmp.append(item.decode())
            self.POST[key] = new_tmp

            if len(self.POST[key]) == 1:
                self.POST[key] = self.POST[key][0]

        for key in request.arguments.keys():
            self.REQUEST[key] = request.arguments[key]

            temp = self.REQUEST[key]
            new_tmp = []
            for item in temp:
                new_tmp.append(item.decode())
            self.REQUEST[key] = new_tmp

            if len(self.REQUEST[key]) == 1:
                self.REQUEST[key] = self.REQUEST[key][0]

        session_value = None
        try:
            session_value = self.COOKIES[settings.SESSION_COOKIE_NAME].value
        except:
            session_value = None

        if session_value:
            print("get session %s" % session_value)
            memstore = MemStore.get_instance()
            try:

                self.session = memstore.get(session_value, False)
                #print "session from django %s" % self.session
                if not self.session:
                    s = Session.objects.get(pk=session_value)
                    information = s.get_decoded()
                    logging.debug("info %s" % information)
                    if information.has_key('user_id'):
                        self.session = information
                        self.user = int(information['user_id'])
                        memstore.set(session_value, self.session)
                    else:
                        self.user = False
                else:
                    if 'user_id' in self.session:
                        self.user = int(self.session['user_id'])
                        
                    else:
                        self.user = False

            except Exception, e:
                logging.debug("_worker problem")
                logging.debug(str(e))
                logging.debug('-' * 60)
                logging.debug(traceback.print_exc())
                logging.debug('-' * 60)
                self.user = False
        else:
            self.user = False
        


# http response class synonym of django response
class HttpResponse(object):
    def __repr__(self):
        return  "%s %s %s" % (self.status_code, self.headers, self.body)
    
    def __init__(self, *args, **kwargs):
        status_code = kwargs.get("status_code", 200)
        body = args[0]
        headers = kwargs.get("headers", [])
        super(HttpResponse, self).__setattr__('status_code', status_code)
        super(HttpResponse, self).__setattr__('body', body)
        d = {}
        for (k, v) in headers:
            d[k] = v
        super(HttpResponse, self).__setattr__('headers', d)

    def get_headers(self):
        for i in self.headers:
            yield (i, self.headers[i])

    def add_header(self, name, value):
        self.headers[name] = value
        return True

    # for easy setting custom headers
    def __setitem__(self, k, v):
        #print "set %s %s" % (k,v)
        if k in ("status_code", "body", "headers"):
            self.__dict__[k] = v
        else:
            self.__dict__["headers"][k] = v

    def set_headers(self, hdrs):
        self.headers = {}
        for (k, v) in hdrs:
            self.headers[k] = v
        return True


# http not allowed class of django response not allowed
class HttpResponseNotAllowed(HttpResponse):
    def __init__(self, not_allowed, *args, **kwargs):
        super(HttpResponse, self).__init__(**kwargs)
        status_code = 405
        not_allowed = not_allowed
        body = "Method not ALLOWED"
        super(HttpResponse, self).__setattr__('status_code', status_code)
        super(HttpResponse, self).__setattr__('body', body)
        super(HttpResponse, self).__setattr__('not_allowed', not_allowed)


class HttpResponseRedirect(HttpResponse):
    def __init__(self, redirect_to, *args, **kwargs):
        super(HttpResponse, self).__init__(**kwargs)
        status_code = 301
        body = "REDIRECT TO "
        super(HttpResponse, self).__setattr__('status_code', status_code)
        super(HttpResponse, self).__setattr__('body', body)
        super(HttpResponse, self).__setattr__('redirect_to', redirect_to)


class HttpResponseServerError(HttpResponse):
    def __init__(self, *args, **kwargs):
        super(HttpResponse, self).__init__(**kwargs)
        status_code = 500
        body = "Error page"
        super(HttpResponse, self).__setattr__('status_code', status_code)
        super(HttpResponse, self).__setattr__('body', body)


# common thread for handlers
class ThreadableMixin:
    def start_worker(self):
        # threading.Thread(target=self.worker).start()
        self.worker()

    def worker(self):
        try:
            self._worker()
        except tornado.web.HTTPError, e:
            logging.debug(str(e))
            self.set_status(e.status_code)

        except Exception, e:
            logging.debug("_worker problem")
            logging.debug(str(e))
            logging.debug('-' * 60)
            logging.debug(traceback.print_exc())
            logging.debug('-' * 60)
            self.set_status(500)

        callable_object = lambda: ThreadableMixin.render_http_response(self)
        tornado.ioloop.IOLoop.instance().add_callback(callable_object)

    # render response to the client
    @staticmethod
    def render_http_response(self):
        self.clear()
        response = self.my_response
        if response.status_code == 301 or response.status_code == 302:
            self.redirect(response.redirect_to, status=response.status_code)
            return
        self.set_status(response.status_code)
        for header in response.get_headers():
            (name, value) = header
            self.add_header(name, value)
        self.write(response.body)
        self.finish()




    # render mistake response to the client
    @staticmethod
    def render_low_level_mistake(self, mistake_body):
        self.clear()
        self.set_status(500)
        self.write(mistake_body)
        self.finish()


# common handler for processing http request through tornado
class CommonRequestHandler(tornado.web.RequestHandler, ThreadableMixin):
    def initialize(self, callable_object, name):
        # callable_object, name
        self.callable = callable_object
        self.url_name = name
        self.my_request = None
        self.my_response = None


    def _worker(self):
        logging.debug("worker is started")
        self.my_response = self.callable(self.my_request)

    @tornado.web.asynchronous
    def get(self):
        self.my_request = HttpRequest(request=self.request, name=self.url_name)
        self.start_worker()

    @tornado.web.asynchronous
    def post(self):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        self.my_request = HttpRequest(request=self.request, name=self.url_name)
        self.start_worker()


class CommonRequestHandlerOneParamNonThread(tornado.web.RequestHandler):
    def initialize(self, callable_object, name):
        logging.debug("initialize")
        self.param1 = None
        self.callable = callable_object
        self.url_name = name
        self.my_request = None
        self.my_response = None

    def _worker(self):
        logging.debug("worker non thread is started")
        self.my_response = self.callable(self.my_request)

    # @tornado.web.asynchronous
    def post(self, param1):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        self.param1 = param1
        self.my_request = HttpRequest(request=self.request, name=self.url_name)
        self._worker()
        self.render_http_response()


    # @tornado.web.asynchronous
    def get(self, param1):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        self.param1 = param1
        self.my_request = HttpRequest(request=self.request, name=self.url_name)
        self._worker()
        self.render_http_response()
        # render response to the client


    def render_http_response(self):
        self.clear()
        response = self.my_response
        if response.status_code == 301 or response.status_code == 302:
            self.redirect(response.redirect_to, status=response.status_code)
            return
        self.set_status(response.status_code)
        for header in response.get_headers():
            (name, value) = header
            self.add_header(name, value)
        self.write(response.body)
        self.finish()


# common handler for processing http request through tornado with one param in url
class CommonRequestHandlerOneParam(tornado.web.RequestHandler, ThreadableMixin):
    def initialize(self, callable_object, name):
        logging.debug("initialize")
        self.param1 = None
        self.callable = callable_object
        self.url_name = name
        self.my_request = None
        self.my_response = None

    def _worker(self):
        self.my_response = self.callable(self.my_request, self.param1)

    @tornado.web.asynchronous
    def post(self, param1):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        self.param1 = param1
        self.my_request = HttpRequest(request=self.request, name=self.url_name)
        self.start_worker()

    @tornado.web.asynchronous
    def get(self, param1):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        self.param1 = param1
        self.my_request = HttpRequest(request=self.request, name=self.url_name)
        self.start_worker()


# common handler for processing http request through tornado with one param in url
class CommonRequestHandlerTwoParam(CommonRequestHandler):
    def initialize(self, *args, **kwargs):
        super(CommonRequestHandler).initialize(*args, **kwargs)

    def post(self, param1, param2):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        response = self.callable(HttpRequest(request=self.request, name=self.url_name), param1, param2)
        self.render_http_response(response)

    def get(self, param1, param2):
        # may context doesn't need all params that we have, and there is some sense to change it to specific object
        response = self.callable(HttpRequest(request=self.request, name=self.url_name), param1, param2)
        self.render_http_response(response)


class Http404(Exception):
    def __init__(self, *args, **kwargs):
        super(Exception).__init__(*args, **kwargs)


# get object or raise 404 not found
def get_object_or_404(TypeClass, id=None):
    try:
        data_model = TypeClass.get(TypeClass.id == id)
        return data_model
    except TypeClass.DoesNotExist:
        raise Http404("does not exist")
