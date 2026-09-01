import pytest
from fastapi import HTTPException

from backend import server


class FakeAuthCli:
    def auth_start(self):
        return {"verification_url": "https://passport.feishu.cn/auth", "device_code": "dev_123456"}

    def auth_complete(self, device_code):
        self.device_code = device_code
        return {"ok": True, "access_token": "secret"}


def test_feishu_auth_start_returns_only_browser_authorization_fields(monkeypatch):
    monkeypatch.setattr(server, "LarkCli", FakeAuthCli)

    response = server.start_feishu_auth()

    assert response == {
        "verificationUrl": "https://passport.feishu.cn/auth",
        "deviceCode": "dev_123456",
    }


def test_feishu_auth_complete_validates_device_code(monkeypatch):
    monkeypatch.setattr(server, "LarkCli", FakeAuthCli)

    assert server.complete_feishu_auth({"deviceCode": "dev_123456"}) == {"ok": True}
    with pytest.raises(HTTPException) as caught:
        server.complete_feishu_auth({"deviceCode": "../bad"})
    assert caught.value.status_code == 400


def test_feishu_folder_browser_returns_only_named_folders(monkeypatch):
    class FakeCli:
        def run(self, args):
            assert args == ["drive", "files", "list", "--page-all", "--as", "user", "--json"]
            return type("Result", (), {"data": {"files": [
                {"type": "docx", "name": "文档", "token": "doc1"},
                {"type": "folder", "name": "项目B", "token": "fld_b"},
                {"type": "folder", "name": "项目A", "token": "fld_a"},
            ]}})()

    monkeypatch.setattr(server, "LarkCli", FakeCli)
    assert server.get_feishu_folders() == {"parentToken": "", "folders": [
        {"token": "fld_a", "name": "项目A"},
        {"token": "fld_b", "name": "项目B"},
    ]}
