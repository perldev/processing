from django.template import Context, loader
from django.http import HttpResponseRedirect, HttpResponse


def banner(Req, Type):
    tmpl = loader.get_template("button.html")
    c = Context({})
    Resp = HttpResponse(tmpl.render(c))
    Resp["Content-Type"] = 'text/html'
    Resp["access-control-allow-origin"] = "*"
    Resp["access-control-allow-methods"] = "GET"
    return Resp


def banner(Req, Type):
    if Type == "one":
        return banner1(Req)

    if Type == "two":
        return banner2(Req)

    if Type == "three":
        return banner3(Req)


def banner1(Req):
    tmpl = loader.get_template("banners/button1.html")
    c = Context({})
    Resp = HttpResponse(tmpl.render(c))
    Resp["Content-Type"] = 'text/html'
    Resp["access-control-allow-origin"] = "*"
    Resp["access-control-allow-methods"] = "GET"
    return Resp


def banner2(Req):
    tmpl = loader.get_template("banners/button2.html")
    c = Context({})
    Resp = HttpResponse(tmpl.render(c))
    Resp["Content-Type"] = 'text/html'
    Resp["access-control-allow-origin"] = "*"
    Resp["access-control-allow-methods"] = "GET"
    return Resp


def banner3(Req):
    tmpl = loader.get_template("banners/button3.html")
    c = Context({})
    Resp = HttpResponse(tmpl.render(c))
    Resp["Content-Type"] = 'text/html'
    Resp["access-control-allow-origin"] = "*"
    Resp["access-control-allow-methods"] = "GET"
    return Resp    
