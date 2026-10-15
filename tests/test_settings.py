from pingmonitor.settings import MAX_HOSTS, parse_hosts


def test_parse_hosts_splits_on_commas_semicolons_and_spaces():
    assert parse_hosts("a.test, b.test;c.test  d.test") == (
        "a.test",
        "b.test",
        "c.test",
        "d.test",
    )


def test_parse_hosts_removes_duplicates_keeping_order():
    assert parse_hosts("b, a, b, a") == ("b", "a")


def test_parse_hosts_empty():
    assert parse_hosts("") == ()
    assert parse_hosts(" , ; ") == ()


def test_parse_hosts_is_capped():
    text = ",".join(f"h{i}" for i in range(MAX_HOSTS + 5))
    assert len(parse_hosts(text)) == MAX_HOSTS
