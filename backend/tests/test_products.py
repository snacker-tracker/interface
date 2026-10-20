"""Tests at the product extraction seam: the OpenFoodFacts parquet and scanned codes in, products out."""

from pathlib import Path

import polars as pl

from food_parquet import food_product, image, write_food_parquet
from snacker.products import extract_products, read_archive, update_products


def products_by_code(food: Path, codes: list[str]) -> dict[str, dict[str, str | None]]:
    products = extract_products(food, codes)
    return {row["code"]: {"name": row["name"], "brands": row["brands"]} for row in products.to_dicts()}


def test_a_product_is_named_by_its_main_name_with_its_brands(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8851959132012", names={"th": "โค๊ก", "main": "Coca Cola", "en": "Coke"},
                     brands="Coke, coca cola"),
    )

    assert products_by_code(food, ["8851959132012"]) == {
        "8851959132012": {"name": "Coca Cola", "brands": "Coke, coca cola"},
    }


def test_without_a_main_name_the_first_name_is_used(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850269522902", names={"th": "แคบหมู", "en": "Crispy Pork Rinds"}),
    )

    assert products_by_code(food, ["8850269522902"])["8850269522902"]["name"] == "แคบหมู"


def test_a_product_with_no_names_has_no_name(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names=None, brands="Singha"))

    assert products_by_code(food, ["8850999220000"]) == {"8850999220000": {"name": None, "brands": "Singha"}}


def test_when_openfoodfacts_lists_a_code_twice_the_first_listing_wins(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda water"}),
        food_product("8850999220000", names={"main": "Club soda"}),
    )

    assert products_by_code(food, ["8850999220000"])["8850999220000"]["name"] == "Soda water"


def test_only_scanned_codes_are_kept(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda water"}, brands="Singha"),
        food_product("3017620422003", names={"main": "Nutella"}, brands="Ferrero"),
    )

    assert list(products_by_code(food, ["8850999220000"])) == ["8850999220000"]


def test_a_code_openfoodfacts_does_not_know_is_kept_with_no_product(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))

    assert products_by_code(food, ["http://oishidrink.com/m/"]) == {
        "http://oishidrink.com/m/": {"name": None, "brands": None},
    }


def test_empty_brands_count_as_no_brands(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8858702410304", names={"main": "Big folly"}, brands=""),
    )

    assert products_by_code(food, ["8858702410304"])["8858702410304"]["brands"] is None


def test_products_are_written_the_first_time(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    products = tmp_path / "products.parquet"

    assert update_products(food, ["8850999220000", "005"], products) is True
    assert pl.read_parquet(products)["code"].to_list() == ["005", "8850999220000"]


def test_the_food_file_is_not_read_again_when_every_code_was_already_looked_up(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000", "005"], products)

    # A missing food file proves it isn't opened.
    assert update_products(tmp_path / "gone.parquet", ["005", "8850999220000"], products) is False


def test_a_newly_scanned_code_triggers_a_fresh_extraction(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda water"}),
        food_product("8851959132012", names={"main": "Coca Cola"}),
    )
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000"], products)

    assert update_products(food, ["8850999220000", "8851959132012"], products) is True
    assert pl.read_parquet(products)["name"].to_list() == ["Soda water", "Coca Cola"]


def test_forcing_extracts_again_even_when_nothing_is_new(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda"}))
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000"], products)
    write_food_parquet(food, food_product("8850999220000", names={"main": "Soda water"}))

    assert update_products(food, ["8850999220000"], products, force=True) is True
    assert pl.read_parquet(products)["name"].to_list() == ["Soda water"]


def product_card(food: Path, code: str) -> dict[str, object]:
    return next(row for row in extract_products(food, [code]).to_dicts() if row["code"] == code)


def test_a_product_card_has_quantity_categories_image_and_link(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product(
            "8850999220000",
            names={"main": "Soda water"},
            quantity="325 ml",
            categories="เครื่องดื่ม, en:Carbonated drinks,en:Carbonated waters",
            lang="th",
            images=[image("1"), image("front_en", rev=6), image("front_th", rev=20), image("nutrition_th", rev=24)],
        ),
    )

    card = product_card(food, "8850999220000")

    assert card["quantity"] == "325 ml"
    assert card["categories"] == ["เครื่องดื่ม", "Carbonated drinks", "Carbonated waters"]
    assert card["image_url"] == "https://images.openfoodfacts.org/images/products/885/099/922/0000/front_th.20.400.jpg"
    assert card["off_url"] == "https://world.openfoodfacts.org/product/8850999220000"


def test_without_a_front_image_in_its_own_language_english_then_any_front_image_is_used(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "A"}, lang="fr",
                     images=[image("front_th", rev=3), image("front_en", rev=6)]),
        food_product("8851959132012", names={"main": "B"}, lang="fr", images=[image("front_th", rev=3)]),
    )

    assert str(product_card(food, "8850999220000")["image_url"]).endswith("/front_en.6.400.jpg")
    assert str(product_card(food, "8851959132012")["image_url"]).endswith("/front_th.3.400.jpg")


def test_short_codes_are_padded_to_13_digits_for_the_image_folder(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("50390168", names={"main": "Mints"}, lang="th", images=[image("front_th", rev=17)]),
    )

    assert product_card(food, "50390168")["image_url"] == (
        "https://images.openfoodfacts.org/images/products/000/005/039/0168/front_th.17.400.jpg"
    )


def test_a_product_without_images_categories_or_quantity_has_none(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8858702410304", names={"main": "Big folly"}, quantity=" ", lang="fr", images=[image("1")]),
    )

    card = product_card(food, "8858702410304")

    assert (card["quantity"], card["categories"], card["image_url"]) == (None, [], None)
    assert card["off_url"] == "https://world.openfoodfacts.org/product/8858702410304"


def test_an_unknown_code_has_no_card_details(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda"}))

    card = product_card(food, "005")

    assert card["known"] is False
    assert (card["quantity"], card["categories"], card["image_url"], card["off_url"]) == (None, None, None, None)


def test_a_products_table_from_before_the_card_details_is_extracted_again(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda"}))
    products = tmp_path / "products.parquet"
    pl.DataFrame({"code": ["8850999220000"], "name": ["Soda"], "brands": [None]},
                 schema={"code": pl.String(), "name": pl.String(), "brands": pl.String()}).write_parquet(products)

    assert update_products(food, ["8850999220000"], products) is True
    assert "image_url" in pl.read_parquet(products).columns


def test_a_front_image_without_a_revision_is_skipped(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda"}, lang="th",
                     images=[image("front_th", rev=None), image("front_en", rev=6)]),
    )

    assert str(product_card(food, "8850999220000")["image_url"]).endswith("/front_en.6.400.jpg")


# --- The Snacker archive: names for products OpenFoodFacts can't name ---


def write_archive(path: Path, *rows: tuple[str, str]) -> Path:
    """A Snacker archive CSV with the real columns; only `code` and `name` matter."""
    lines = ["code,name,created_at,updated_at,url,categories"]
    lines += [f'{code},"{name}",2019-10-31 09:34:37.713+00,2019-10-31 09:34:37.713+00,,' for code, name in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def names_by_code(food: Path, codes: list[str], archive: Path | None) -> dict[str, tuple[str | None, str | None]]:
    """code -> (name, name_source)."""
    products = extract_products(food, codes, archive=read_archive(archive) if archive else None)
    return {row["code"]: (row["name"], row["name_source"]) for row in products.to_dicts()}


def test_the_archive_names_a_code_openfoodfacts_does_not_know(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    archive = write_archive(tmp_path / "codes.csv", ("220000", "Singha soda 325 ml"))

    assert names_by_code(food, ["220000", "8850999220000"], archive) == {
        "220000": ("Singha soda 325 ml", "snacker-archive"),
        "8850999220000": ("Soda water", "openfoodfacts"),
    }


def test_an_openfoodfacts_name_beats_the_archive(tmp_path: Path) -> None:
    # Some archive names were scraped against the wrong barcode.
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8886467100017", names={"main": "Pringles original"}))
    archive = write_archive(tmp_path / "codes.csv", ("8886467100017", "Fashion Vintage Ladies Hot Pants"))

    assert names_by_code(food, ["8886467100017"], archive) == {"8886467100017": ("Pringles original", "openfoodfacts")}


def test_the_archive_names_a_product_openfoodfacts_has_without_a_name(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names=None, brands="Singha"))
    archive = write_archive(tmp_path / "codes.csv", ("8850999220000", "  Singha soda water "))

    products = extract_products(food, ["8850999220000"], archive=read_archive(archive)).to_dicts()

    assert [(row["name"], row["name_source"], row["known"], row["brands"]) for row in products] == [
        ("Singha soda water", "snacker-archive", True, "Singha"),
    ]


def test_a_code_the_archive_records_twice_gets_no_archive_name(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    archive = write_archive(
        tmp_path / "codes.csv",
        ("5", "Ratatouille à la provençale"), ("5", "Otto coffee maker"), ("78", "Isan sausage"), ("78", "Taro fish snack"),
        ("152", "Curry paste"),
    )

    assert read_archive(archive).duplicated == ["5", "78"]
    assert names_by_code(food, ["5", "152"], archive) == {"152": ("Curry paste", "snacker-archive"), "5": (None, None)}


def test_without_the_archive_names_come_from_openfoodfacts_only(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))

    assert names_by_code(food, ["220000", "8850999220000"], archive=None) == {
        "220000": (None, None),
        "8850999220000": ("Soda water", "openfoodfacts"),
    }


def test_archive_names_are_kept_when_the_food_file_is_not_read_again(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda water"}))
    archive = read_archive(write_archive(tmp_path / "codes.csv", ("220000", "Singha soda 325 ml")))
    products = tmp_path / "products.parquet"
    update_products(food, ["220000", "8850999220000"], products, archive=archive)

    assert update_products(tmp_path / "gone.parquet", ["220000"], products, archive=archive) is False
    assert pl.read_parquet(products)["name"].to_list() == ["Singha soda 325 ml", "Soda water"]


def test_a_product_has_its_openfoodfacts_grades(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda"},
                     nutriscore_grade="b", nova_group=4, environmental_score_grade="d"),
    )

    card = product_card(food, "8850999220000")

    assert (card["nutri_score"], card["nova_group"], card["green_score"]) == ("B", 4, "D")


def test_grades_openfoodfacts_could_not_work_out_are_no_grades(tmp_path: Path) -> None:
    food = write_food_parquet(
        tmp_path / "food.parquet",
        food_product("8850999220000", names={"main": "Soda"},
                     nutriscore_grade="unknown", nova_group=None, environmental_score_grade="not-applicable"),
        food_product("8851959132012", names={"main": "Water"}, nutriscore_grade="", environmental_score_grade=None),
    )

    for code in ("8850999220000", "8851959132012"):
        card = product_card(food, code)
        assert (card["nutri_score"], card["nova_group"], card["green_score"]) == (None, None, None)


def test_an_unknown_product_has_no_grades(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda"},
                                                                      nutriscore_grade="a"))

    card = product_card(food, "005")

    assert (card["nutri_score"], card["nova_group"], card["green_score"]) == (None, None, None)


def test_a_products_table_from_before_the_grades_is_extracted_again(tmp_path: Path) -> None:
    food = write_food_parquet(tmp_path / "food.parquet", food_product("8850999220000", names={"main": "Soda"},
                                                                      nutriscore_grade="c"))
    products = tmp_path / "products.parquet"
    update_products(food, ["8850999220000"], products)
    pl.read_parquet(products).drop("nutri_score", "nova_group", "green_score").write_parquet(products)

    assert update_products(food, ["8850999220000"], products) is True
    assert pl.read_parquet(products)["nutri_score"].to_list() == ["C"]
