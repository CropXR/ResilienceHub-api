from django.http import HttpResponse
from django.template import loader
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..v2.serializers import InvestigationSerializer
from .services import InvestigationService


# for each model
    # api
        # create service model
        # use serializer
        # return response

    # templates
        # parse service model(s) to template


class InvestigationViewSet(ModelViewSet):
    serializer_class = InvestigationSerializer
    lookup_field = 'accession_code'
    lookup_value_regex = 'CXRP[0-9]+'

    def get_queryset(self):
        return InvestigationService.list(self.request.user)

    def get_object(self):
        return InvestigationService.get(user=self.request.user, accession_code=self.kwargs[self.lookup_field])

    def perform_create(self, serializer):
        InvestigationService.create(user=self.request.user, serializer=serializer)

    # how are contributors added from the view?


def catalogue_api(request) -> Response:
    investigations = InvestigationService.list(request.user)
    serializer = InvestigationSerializer(investigations, context={'request': request}, many=True)
    return Response(serializer.data)


def catalogue_html(request) -> HttpResponse:
  investigations = InvestigationService.list(request.user)
  template = loader.get_template('catalogue.html')
  context = {'investigations': investigations}
  return HttpResponse(template.render(context, request))


def index_html(request) -> HttpResponse:
    template = loader.get_template('index.html')
    return HttpResponse(template.render({}, request))
