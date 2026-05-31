"""Unit tests for profile endpoint SQL source tables."""

from api import queries


class RecordingCursor:
    def __init__(self):
        self.sql = ""
        self.params = ()

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params

    def fetchall(self):
        return []

    def fetchone(self):
        return None

    def close(self):
        pass


class RecordingConnection:
    def __init__(self):
        self.cursor_obj = RecordingCursor()

    def cursor(self, dictionary=False):
        return self.cursor_obj


def test_profile_list_reads_from_snapshot():
    conn = RecordingConnection()

    queries.list_neighborhoods(conn)

    assert "FROM neighborhood_profile_snapshot" in conn.cursor_obj.sql
    assert "vw_neighborhood_profile" not in conn.cursor_obj.sql
    assert "ORDER BY community_name" in conn.cursor_obj.sql


def test_profile_detail_reads_from_snapshot_by_primary_key():
    conn = RecordingConnection()

    queries.get_neighborhood(conn, 1)

    assert "FROM neighborhood_profile_snapshot" in conn.cursor_obj.sql
    assert "WHERE community_id = %s" in conn.cursor_obj.sql
    assert conn.cursor_obj.params == (1,)


def test_profile_compare_reads_from_snapshot():
    conn = RecordingConnection()

    queries.compare_neighborhoods(conn, [1, 2, 3])

    assert "FROM neighborhood_profile_snapshot" in conn.cursor_obj.sql
    assert "WHERE community_id IN (%s, %s, %s)" in conn.cursor_obj.sql
    assert "ORDER BY FIELD(community_id, %s, %s, %s)" in conn.cursor_obj.sql
    assert conn.cursor_obj.params == (1, 2, 3, 1, 2, 3)
