import traceback

from django.core.paginator import Paginator, EmptyPage
from rest_framework import viewsets
from activity.models import activity
from activity.serializer import ActivitySerializer
from utils.customClass import JSONResponse, InvestError
from utils.util import SuccessResponse, InvestErrorResponse, ExceptionResponse, returnListChangeToLanguage


class ActivityView(viewsets.ModelViewSet):
    queryset = activity.objects.filter(is_deleted=False)
    serializer_class = ActivitySerializer

    def list(self, request, *args, **kwargs):
        try:
            lang = request.GET.get('lang')
            page_size = request.GET.get('page_size')
            page_index = request.GET.get('page_index')
            if not page_size:
                page_size = 10
            if not page_index:
                page_index = 1
            queryset = self.filter_queryset(self.get_queryset())
            sort = request.GET.get('sort', None)
            if sort not in ['True', 'true', True, 1, 'Yes', 'yes', 'YES', 'TRUE']:
                queryset = queryset.order_by('index', )
            else:
                queryset = queryset.order_by('-index', )
            count = queryset.count()
            try:
                queryset = Paginator(queryset, page_size)
                queryset = queryset.page(page_index)
            except EmptyPage:
                return JSONResponse(SuccessResponse({'count': 0, 'data': []}))
            serializer = self.serializer_class(queryset, many=True)
            return JSONResponse(SuccessResponse({'count': count, 'data':returnListChangeToLanguage(serializer.data, lang)}))
        except InvestError as err:
            return JSONResponse(InvestErrorResponse(err))
        except Exception:
            return JSONResponse(ExceptionResponse(traceback.format_exc().split('\n')[-2]))