from django.test import TestCase
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from ..models import MinigameLog


class MinigameUserStatsTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='tester', password='pass')
        self.user_id_str = str(self.user.id)
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)

    def test_xp_and_coins_aggregation_with_clientid(self):
        # appid 'a' has two records for clientid 'c1' (best score should be used)
        MinigameLog.objects.create(
            msgtype='RESULT',
            key='k1',
            tsms=1000,
            user=self.user_id_str,
            payload={'appid': 'a', 'clientid': 'c1', 'score': 50, 'xp': 10, 'bonus_xp': 2, 'coin': 5, 'bonus_coin': 1},
        )
        MinigameLog.objects.create(
            msgtype='RESULT',
            key='k2',
            tsms=2000,
            user=self.user_id_str,
            payload={'appid': 'a', 'clientid': 'c1', 'score': 100, 'xp': 20, 'bonus_xp': 3, 'coin': 8, 'bonus_coin': 2},
        )

        # appid 'b' for same client
        MinigameLog.objects.create(
            msgtype='RESULT',
            key='k3',
            tsms=1500,
            user=self.user_id_str,
            payload={'appid': 'b', 'clientid': 'c1', 'score': 70, 'xp': 15, 'bonus_xp': 0, 'coin': 4, 'bonus_coin': 0},
        )

        # A record with a different clientid should not affect total_xp for c1
        MinigameLog.objects.create(
            msgtype='RESULT',
            key='k4',
            tsms=3000,
            user=self.user_id_str,
            payload={'appid': 'a', 'clientid': 'c2', 'score': 999, 'xp': 999, 'bonus_xp': 1, 'coin': 100, 'bonus_coin': 0},
        )

        # Request stats for clientid c1
        resp = self.client.get('/api/minigames/user-stats/', {'clientid': 'c1'})
        self.assertEqual(resp.status_code, 200)
        data = resp.json()

        # total_xp: appid 'a' best for c1 -> xp 20+3 = 23; appid 'b' -> 15+0 = 15 => 38
        self.assertEqual(data.get('total_xp'), 38)

        # total_coins: best per appid system-wide -> appid 'a' best is score 999 coin 100+0 = 100; appid 'b' coin 4 => 104
        self.assertEqual(data.get('total_coins'), 104)


