from django.test import TestCase, Client
from django.urls import reverse


class LocationsAPITest(TestCase):
    def setUp(self):
        self.client = Client()

    def test_provinces_list(self):
        url = reverse('province-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        # Expect at least one province from locations.json
        self.assertGreaterEqual(len(data), 1)

    def test_districts_requires_province(self):
        url = reverse('district-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_districts_list_by_province(self):
        url = reverse('district-list') + '?province=koshi_province'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        # Morang and Sunsari are in koshi_province in locations.json
        labels = [d.get('label') for d in data]
        self.assertIn('Morang', labels)
        self.assertIn('Sunsari', labels)

    def test_municipalities_requires_district(self):
        url = reverse('municipality-list')
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 400)

    def test_municipalities_list_by_district(self):
        url = reverse('municipality-list') + '?district=morang'
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIsInstance(data, list)
        labels = [m.get('label') for m in data]
        self.assertIn('Biratnagar Municipality', labels)
