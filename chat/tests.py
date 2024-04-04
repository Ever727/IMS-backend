from django.test import TestCase
from channels.testing import ChannelsLiveServerTestCase, WebsocketCommunicator
from tasright_backend.asgi import application
from asgiref.sync import sync_to_async

# Create your tests here.

class TrueTests(TestCase):
    def test_true(self):
        self.assertTrue(True)

