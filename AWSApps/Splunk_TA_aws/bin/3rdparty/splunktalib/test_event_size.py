import event_writer as ew
import credentials as cred


config = {
    "use_hec": True,
    "token": "A0-5800-406B-9224-8E1DC4E720B7",
    "hec_server_uri": "https://localhost:8088",
    "server_uri": "https://localhost:8089",
    "session_key": cred.CredentialManager.get_session_key("admin", "admin")
}

siz = 1024 * 1024 + 100
event = {
    "event": "x" * siz,
    "index": "main",
    "host": "localhost",
    "source": "test",
    "sourcetype": "testbig",
}

writer = ew.create_event_writer(config)
writer.write_events([event])
