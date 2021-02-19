from utils.customClass import JSONResponse, InvestError
from utils.util import InvestErrorResponse, setrequestuser

try:
    from django.utils.deprecation import MiddlewareMixin  # Django 1.10.x
except ImportError:
    MiddlewareMixin = object  # Django 1.4.x - Django 1.9.x

blackIPlist = []
class IpMiddleware(MiddlewareMixin):
    def process_request(self, request):
        # source = request.META.get('HTTP_SOURCE')
        # if source is not None:
        #     pass
        # else:
        #     return JSONResponse(InvestErrorResponse(InvestError(8888,msg='source unknown')))
        # clienttype = request.META.get('HTTP_CLIENTTYPE')
        # if clienttype and isinstance(clienttype,(str,int,unicode)) and clienttype in [1,2,3,4,'1','2','3','4']:
        #     pass
        # else:
        #     return JSONResponse(InvestErrorResponse(InvestError(code=3007)))
        setrequestuser(request)
        if request.META.has_key('HTTP_X_FORWARDED_FOR'):
            ip = request.META['HTTP_X_FORWARDED_FOR']
        else:
            ip = request.META['REMOTE_ADDR']
        if ip:
            if ip in blackIPlist:
                return JSONResponse(InvestErrorResponse(InvestError(code=3005)))
            else:
                return None
        else:
            return JSONResponse(InvestErrorResponse(InvestError(code=3006)))
