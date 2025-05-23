from django.http import HttpResponse
from django.template import loader
from rest_framework.viewsets import ModelViewSet

from api.v2.serializers import InvestigationSerializer
from api.v3.services import InvestigationService


# for each model
    # api
        # create service model
        # use serializer
        # return response

    # templates
        # parse service model(s) to template


class InvestigationViewSet(ModelViewSet):
    serializer_class = InvestigationSerializer

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(InvestigationService.list(request.user))
        serializer = InvestigationSerializer(queryset, many=True)
        return HttpResponse(serializer.data)


# alternative to viewset above
def catalogue_api(request) -> HttpResponse:
    investigations = InvestigationService.list()
    serializer = InvestigationSerializer
    return HttpResponse(serializer.data)


def catalogue_html(request) -> HttpResponse:
  investigations = InvestigationService.list(request.user)
  template = loader.get_template('catalogue.html')
  context = {'investigations': investigations}
  return HttpResponse(template.render(context, request))


def index_html(request) -> HttpResponse:
    template = loader.get_template('index.html')
    return HttpResponse(template.render({}, request))