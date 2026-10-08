import pytest

from app.content import repository as r


def test_create_and_list_deck(conn):
    deck_id = r.create_deck(conn, "Spanish", "verbs")
    decks = r.list_decks(conn)
    assert len(decks) == 1
    assert decks[0]["id"] == deck_id
    assert decks[0]["name"] == "Spanish"
    assert decks[0]["description"] == "verbs"
    assert decks[0]["card_count"] == 0


def test_create_deck_blank_name_raises(conn):
    with pytest.raises(ValueError):
        r.create_deck(conn, "   ")
    assert r.list_decks(conn) == []


def test_list_decks_counts_cards(conn):
    deck_id = r.create_deck(conn, "Spanish")
    r.create_card(conn, deck_id, "hola", "hello")
    r.create_card(conn, deck_id, "adios", "bye")
    assert r.list_decks(conn)[0]["card_count"] == 2


def test_get_deck_missing_returns_none(conn):
    assert r.get_deck(conn, 999) is None


def test_delete_deck_returns_true_then_false(conn):
    deck_id = r.create_deck(conn, "Spanish")
    assert r.delete_deck(conn, deck_id) is True
    assert r.delete_deck(conn, deck_id) is False
    assert r.get_deck(conn, deck_id) is None


def test_create_card(conn):
    deck_id = r.create_deck(conn, "Spanish")
    card_id = r.create_card(conn, deck_id, " hola ", "hello")
    card = r.get_card(conn, card_id)
    assert card["deck_id"] == deck_id
    assert card["front"] == "hola"
    assert card["back"] == "hello"


def test_create_card_blank_front_raises(conn):
    deck_id = r.create_deck(conn, "Spanish")
    with pytest.raises(ValueError):
        r.create_card(conn, deck_id, "", "hello")
    with pytest.raises(ValueError):
        r.create_card(conn, deck_id, "hola", "  ")
    assert r.list_cards(conn, deck_id) == []


def test_create_card_in_missing_deck_raises(conn):
    with pytest.raises(LookupError):
        r.create_card(conn, 999, "hola", "hello")


def test_list_cards_ordered_by_id(conn):
    deck_id = r.create_deck(conn, "Spanish")
    ids = [r.create_card(conn, deck_id, f"front {i}", f"back {i}") for i in range(3)]
    assert [card["id"] for card in r.list_cards(conn, deck_id)] == ids
    assert r.list_card_ids(conn, deck_id) == ids


def test_list_cards_only_from_that_deck(conn):
    spanish = r.create_deck(conn, "Spanish")
    chem = r.create_deck(conn, "Chem")
    r.create_card(conn, spanish, "hola", "hello")
    r.create_card(conn, chem, "H2O", "water")
    assert [c["front"] for c in r.list_cards(conn, spanish)] == ["hola"]
    assert [c["front"] for c in r.list_cards(conn, chem)] == ["H2O"]


def test_update_card(conn):
    deck_id = r.create_deck(conn, "Spanish")
    card_id = r.create_card(conn, deck_id, "hola", "hello")
    assert r.update_card(conn, card_id, "hola", "hi") is True
    assert r.get_card(conn, card_id)["back"] == "hi"
    assert r.update_card(conn, 999, "x", "y") is False
    with pytest.raises(ValueError):
        r.update_card(conn, card_id, "", "hi")


def test_delete_card(conn):
    deck_id = r.create_deck(conn, "Spanish")
    card_id = r.create_card(conn, deck_id, "hola", "hello")
    assert r.delete_card(conn, card_id) is True
    assert r.delete_card(conn, card_id) is False
    assert r.get_card(conn, card_id) is None


def test_delete_deck_cascades_cards(conn):
    deck_id = r.create_deck(conn, "Spanish")
    card_id = r.create_card(conn, deck_id, "hola", "hello")
    r.delete_deck(conn, deck_id)
    assert r.get_card(conn, card_id) is None
    assert r.list_cards(conn, deck_id) == []
