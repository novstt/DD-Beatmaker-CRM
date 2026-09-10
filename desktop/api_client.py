import requests

class ApiClient:
    def __init__(self, base_url="https://dd-beatmaker-crm.onrender.com"):
        self.base_url = base_url.rstrip("/")
        self.token = None
        self.user = None
        self._cache = {}
        self._cache_time = {}

    def _invalidate(self, *keys):
        for key in keys:
            self._cache.pop(key, None)
            self._cache_time.pop(key, None)
            # Invalidate parameterized cache entries such as beats:<search>
            for cached_key in list(self._cache.keys()):
                if cached_key == key or cached_key.startswith(f"{key}:"):
                    self._cache.pop(cached_key, None)
                    self._cache_time.pop(cached_key, None)

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"} if self.token else {}

    def _request(self, method, path, **kwargs):
        try:
            response = requests.request(
                method, self.base_url + path,
                headers=self._headers(), timeout=30, **kwargs
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"Network error: {exc}") from exc
        if not response.ok:
            try:
                detail = response.json().get("detail")
            except Exception:
                detail = response.text
            raise RuntimeError(f"HTTP {response.status_code}: {detail}")
        if not response.content:
            return None
        content_type = response.headers.get("content-type", "").lower()
        if "application/json" in content_type:
            return response.json()
        return response.text

    def register(self, username, email, password):
        return self._request(
            "POST",
            "/api/auth/register",
            json={
                "username": username,
                "email": email,
                "password": password,
            },
        )

    def login(self, email, password):
        data = self._request("POST", "/api/auth/login",
                             json={"email": email, "password": password})
        self.token = data["access_token"]
        try:
            self.user = self._request("GET", "/api/auth/me")
        except Exception:
            self.user = {}
        return self.user

    def refresh_session(self, clear_cache=True):
        if not self.token:
            return None
        if clear_cache:
            self._cache.clear(); self._cache_time.clear()
        self.user = self._request("GET", "/api/auth/me")
        return self.user

    def my_artists(self, search="", limit=100, offset=0):
        key=f"artists:{search.strip().casefold()}:{limit}:{offset}"
        if not search.strip() and key in self._cache:return self._cache[key]
        data=self._request("GET", "/api/artists/mine", params={"search": search, "limit": limit, "offset": offset})
        if not search.strip():self._cache[key]=data
        return data

    def global_artists(self, search="", limit=100, offset=0):
        return self._request("GET", "/api/artists/global", params={"search": search, "limit": limit, "offset": offset})

    def update_artist(
        self,
        artist_id,
        platform,
        artist_username,
        message_status,
        cash_ready,
        notes="",
    ):
        return self._request(
            "PUT",
            f"/api/artists/{artist_id}/contact",
            json={
                "platform": platform,
                "artist_username": artist_username,
                "message_status": message_status,
                "beat_ids": [],
                "cash_ready": cash_ready,
                "notes": notes or None,
            },
        )

    def delete_artist(self, artist_id):
        return self._request("DELETE", f"/api/artists/{artist_id}")

    def add_artist(self, name, platform, artist_username, message_status,
                   beat_ids, cash_ready, notes=""):
        artist = self._request("POST", "/api/artists", json={
            "name": name, "platform": platform,
            "artist_username": artist_username,
            "message_status": message_status,
            "cash_ready": cash_ready, "notes": notes or None
        })
        if beat_ids:
            self._request("POST", f"/api/artists/{artist['id']}/contact", json={
                "platform": platform,
                "artist_username": artist_username,
                "message_status": message_status,
                "beat_ids": beat_ids,
                "cash_ready": cash_ready,
                "notes": notes or None
            })
        self._invalidate("artists")
        return artist

    def producer_check(self, username):
        return self._request("GET", "/api/beats/producer-check", params={"username": username})

    def messenger_check(self, username):
        """Resolve a registered Messenger against the production API."""
        return self._request(
            "GET", "/api/licenses/messenger-check",
            params={"username": username},
        )

    def create_beat(self, name, bpm, musical_key, status, producer_username=None, co_producer_usernames=None):
        result=self._request("POST","/api/beats",json={"name":name,"bpm":bpm,"musical_key":musical_key,"status":status,"producer_username":producer_username,"co_producer_usernames":co_producer_usernames or []})
        self._invalidate("beats"); return result

    def update_beat(self, beat_id, name, bpm, musical_key, status, producer_username=None, co_producer_usernames=None):
        result=self._request("PUT",f"/api/beats/{beat_id}",json={"name":name,"bpm":bpm,"musical_key":musical_key,"status":status,"producer_username":producer_username,"co_producer_usernames":co_producer_usernames or []})
        self._invalidate("beats"); return result

    def delete_beat(self, beat_id):
        result=self._request("DELETE", f"/api/beats/{beat_id}"); self._invalidate("beats"); return result

    def send_beat(self, artist_id, beat_id):
        return self._request(
            "POST", "/api/beats/send",
            json={"artist_id": artist_id, "beat_id": beat_id},
        )

    def beats(self, search="", limit=100, offset=0):
        key=f"beats:{search.strip().casefold()}:{limit}:{offset}"
        if not search.strip() and key in self._cache: return self._cache[key]
        data=self._request("GET", "/api/beats", params={"search": search, "limit": limit, "offset": offset})
        if not search.strip(): self._cache[key]=data
        return data

    def dashboard(self, period="all"):
        return self._request(
            "GET",
            "/api/stats/dashboard",
            params={"period": period},
        )

    def get_artist(self, artist_id):
        return self._request("GET", f"/api/artists/{artist_id}/details")


    def notifications(self):
        return self._request("GET", "/api/notifications")

    def unread_notifications(self):
        return [n for n in self.notifications() if not n.get("is_read")]

    def mark_notification_read(self, notification_id):
        return self._request(
            "POST", f"/api/notifications/{notification_id}/read"
        )

    def mark_all_notifications_read(self):
        return self._request("POST", "/api/notifications/read-all")

    def licenses(self):
        if "licenses" not in self._cache:self._cache["licenses"]=self._request("GET", "/api/licenses")
        return self._cache["licenses"]

    def license_history(self, license_id):
        return self._request("GET", f"/api/licenses/{license_id}/history")

    def update_license_status(self, license_id, new_status):
        result = self._request("PUT", f"/api/licenses/{license_id}/status", params={"new_status": new_status})
        self._invalidate("licenses")
        return result

    def create_license(self, artist_id, beat_id, license_type, price, status="paid", notes="", is_producer=False, is_messenger=False, producer_share_percent=0, mailing_share_percent=0, currency="USD", messenger_username=None):
        result = self._request(
            "POST",
            "/api/licenses",
            json={
                "artist_id": artist_id,
                "beat_id": beat_id,
                "license_type": license_type,
                "price": price,
                "currency": currency,
                "status": status,
                "notes": notes or None,
                "messenger_username": messenger_username or None,
            },
        )
        self._invalidate("licenses")
        return result

    def loop_sends(self):
        return self._request("GET", "/api/workspace/loop-sends")

    def create_loop_send(self, artist_id, source, artist_username, loop_name, audio_filename=None, audio_path=None, notes="", reminder_at=None):
        result=self._request("POST","/api/workspace/loop-sends",json={"artist_id":artist_id,"source":source or None,"artist_username":artist_username or None,"loop_name":loop_name,"audio_filename":audio_filename,"audio_path":audio_path,"notes":notes or None,"reminder_at":reminder_at})
        return result

    def done_loop_send(self, item_id):
        return self._request("POST", f"/api/workspace/loop-sends/{item_id}/done")

    def non_profit_tracks(self):
        return self._request("GET", "/api/workspace/non-profit-tracks")

    def create_non_profit_track(self, artist_id, track_name, audio_filename=None, audio_path=None, purchase_intent="unknown", uploaded_platform=None, upload_url=None, notes=""):
        return self._request("POST","/api/workspace/non-profit-tracks",json={"artist_id":artist_id,"track_name":track_name,"audio_filename":audio_filename,"audio_path":audio_path,"purchase_intent":purchase_intent,"uploaded_platform":uploaded_platform,"upload_url":upload_url,"notes":notes or None})

    def mixing_services(self):
        return self._request("GET", "/api/workspace/mixing")

    def create_mixing(self, license_id, mixer_username=None, mixer_name=None, price=0, currency="USD", notes=""):
        return self._request("POST","/api/workspace/mixing",json={"license_id":license_id,"mixer_username":mixer_username or None,"mixer_name":mixer_name or None,"price":price,"currency":currency,"notes":notes or None})

    def due_reminders(self):
        return self._request("GET", "/api/workspace/reminders/due")

    def workspace_overview(self):
        return self._request("GET", "/api/workspace/overview")


    def artist_timeline(self, artist_id):
        return self._request("GET", f"/api/workspace/artists/{artist_id}/timeline")

    def create_followup(self, artist_id, due_at, title="Follow up", notes=""):
        return self._request("POST", "/api/workspace/followups", json={"artist_id":artist_id,"due_at":due_at,"title":title,"notes":notes or None})

    def complete_followup(self, followup_id):
        return self._request("POST", f"/api/workspace/followups/{followup_id}/done")

    def create_goal(self, title, target, current=0, period="month", currency="USD"):
        return self._request("POST", "/api/workspace/goals", json={"title":title,"target":target,"current":current,"period":period,"currency":currency})

    def update_goal(self, goal_id, title, target, current=0, period="month", currency="USD"):
        return self._request("PUT", f"/api/workspace/goals/{goal_id}", json={"title":title,"target":target,"current":current,"period":period,"currency":currency})

    def delete_goal(self, goal_id):
        return self._request("DELETE", f"/api/workspace/goals/{goal_id}")

    def toggle_favorite(self, entity_type, entity_id):
        return self._request("POST", "/api/workspace/favorites", json={"entity_type":entity_type,"entity_id":entity_id})

    def favorites(self):
        return self._request("GET", "/api/workspace/favorites")

    def add_tag(self, beat_id, tag):
        return self._request("POST", f"/api/workspace/beats/{beat_id}/tags", json={"name":tag})

    def bulk_update_beats(self, beat_ids, bpm=None, musical_key=None, status=None, add_tag=None):
        payload = {"beat_ids": list(map(int, beat_ids))}
        if bpm is not None: payload["bpm"] = int(bpm)
        if musical_key is not None: payload["musical_key"] = musical_key
        if status is not None: payload["status"] = status
        if add_tag: payload["add_tag"] = add_tag
        result = self._request("POST", "/api/beats/bulk-update", json=payload)
        self._invalidate("beats")
        return result

    def permanent_delete(self, entity_type, entity_id):
        result = self._request("DELETE", f"/api/workspace/trash/{entity_type}/{entity_id}/permanent")
        self._invalidate("artists", "beats", "licenses")
        return result

    def beat_tags(self, beat_id):
        return self._request("GET", f"/api/workspace/beats/{beat_id}/tags")

    def trash(self):
        return self._request("GET", "/api/workspace/trash")

    def restore(self, entity_type, entity_id):
        return self._request("POST", f"/api/workspace/trash/{entity_type}/{entity_id}/restore")

    def export_backup(self):
        return self._request("GET", "/api/workspace/backup/export")

    def health(self):
        return self._request("GET", "/health")

    def app_version(self):
        return self._request("GET", "/api/system/version")

    def admin_audit(self):
        return self._request("GET", "/api/admin/audit")

    def admin_health(self):
        return self._request("GET", "/api/admin/health")

    def license_versions(self, license_id):
        return self._request("GET", f"/api/licenses/{license_id}/versions")

    def license_splits(self, license_id):
        return self._request("GET", f"/api/licenses/{license_id}/splits")

    def license_financial_summary(self, license_id):
        return self._request("GET", f"/api/licenses/{license_id}/financial-summary")

    def artist_score(self, artist_id):
        return self._request("GET", f"/api/workspace/artists/{artist_id}/score")

    def import_backup(self, payload):
        return self._request("POST", "/api/workspace/backup/import", json=payload)

    def admin_overview(self):
        return self._request("GET", "/api/admin/overview")

    def admin_users(self):
        return self._request("GET", "/api/admin/users")

    def admin_toggle_user(self, user_id):
        return self._request("POST", f"/api/admin/users/{user_id}/toggle")

    def logout(self):
        self.token = None
        self.user = None
        self._cache = {}
        self._cache_time = {}

    def update_settings(self, theme=None, currency=None):
        payload = {}
        if theme is not None:
            payload["theme"] = theme
        if currency is not None:
            payload["currency"] = currency
        result = self._request("PUT", "/api/auth/settings", json=payload)
        self.user = result
        return result
