"""Seed the synthetic merchant catalog. Idempotent: upserts by stable ID, so
re-running never duplicates and never clobbers Phase 4's poisoned listings."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy.dialects.postgresql import insert  # noqa: E402

from gateway.db import get_session_factory  # noqa: E402
from gateway.models import Merchant, Product  # noqa: E402

MERCHANTS = [
    ("m_voltedge", "VoltEdge Electronics", "electronics"),
    ("m_chaiwala", "Chaiwala & Co", "food_beverage"),
    ("m_threadly", "Threadly Fashion", "apparel"),
    ("m_pagesnbind", "Pages & Bind", "books"),
    ("m_fitkart", "FitKart Sports", "sports"),
    ("m_homely", "Homely Living", "home_goods"),
]

# (id, merchant, title, description, price_paise)
PRODUCTS = [
    (
        "p_earbuds_anc",
        "m_voltedge",
        "NoiseFree ANC Earbuds",
        "Wireless earbuds with active noise cancellation, 28h battery.",
        189_900,
    ),
    (
        "p_powerbank_20k",
        "m_voltedge",
        "20000mAh Power Bank",
        "Fast-charge power bank, dual USB-C output.",
        149_900,
    ),
    (
        "p_smartwatch_s2",
        "m_voltedge",
        "PulseFit S2 Smartwatch",
        "AMOLED display, SpO2 and sleep tracking.",
        259_900,
    ),
    (
        "p_btspeaker_go",
        "m_voltedge",
        "GoBeat Bluetooth Speaker",
        "IPX7 waterproof portable speaker, 12h playtime.",
        119_900,
    ),
    (
        "p_usbc_hub",
        "m_voltedge",
        "7-in-1 USB-C Hub",
        "HDMI 4K, 3x USB-A, SD card reader, 100W PD.",
        84_900,
    ),
    (
        "p_keyboard_mech",
        "m_voltedge",
        "TactiKey Mechanical Keyboard",
        "Hot-swappable switches, RGB, compact 75% layout.",
        329_900,
    ),
    (
        "p_mouse_ergo",
        "m_voltedge",
        "ErgoGlide Wireless Mouse",
        "Vertical ergonomic mouse, silent clicks.",
        99_900,
    ),
    (
        "p_masala_chai",
        "m_chaiwala",
        "Masala Chai Blend 500g",
        "Assam CTC with cardamom, ginger and cinnamon.",
        34_900,
    ),
    (
        "p_green_tea",
        "m_chaiwala",
        "Himalayan Green Tea 100 bags",
        "Whole-leaf green tea from Darjeeling estates.",
        44_900,
    ),
    (
        "p_filter_coffee",
        "m_chaiwala",
        "Mysore Filter Coffee 250g",
        "80:20 coffee-chicory blend, freshly roasted.",
        29_900,
    ),
    (
        "p_kulhad_set",
        "m_chaiwala",
        "Kulhad Cup Set of 6",
        "Handmade clay cups for authentic chai service.",
        54_900,
    ),
    (
        "p_honey_raw",
        "m_chaiwala",
        "Raw Forest Honey 500g",
        "Unprocessed honey from Sundarbans apiaries.",
        64_900,
    ),
    (
        "p_snack_box",
        "m_chaiwala",
        "Evening Snacks Box",
        "Assorted namkeen and biscuits, 12 packs.",
        79_900,
    ),
    (
        "p_tshirt_oversized",
        "m_threadly",
        "Oversized Cotton Tee",
        "240 GSM heavyweight cotton, garment dyed.",
        89_900,
    ),
    (
        "p_jeans_slim",
        "m_threadly",
        "Slim Fit Stretch Jeans",
        "Mid-rise, 4-way stretch denim.",
        189_900,
    ),
    (
        "p_hoodie_zip",
        "m_threadly",
        "Zip-Up Fleece Hoodie",
        "Brushed fleece, kangaroo pockets.",
        159_900,
    ),
    (
        "p_kurta_linen",
        "m_threadly",
        "Linen Blend Kurta",
        "Breathable summer kurta, mandarin collar.",
        129_900,
    ),
    (
        "p_sneakers_court",
        "m_threadly",
        "Court Classic Sneakers",
        "Vegan leather, cushioned insole.",
        249_900,
    ),
    ("p_cap_dad", "m_threadly", "Embroidered Dad Cap", "Adjustable cotton twill cap.", 49_900),
    (
        "p_socks_5pack",
        "m_threadly",
        "Crew Socks 5-Pack",
        "Combed cotton, reinforced heel.",
        39_900,
    ),
    (
        "p_book_pragmatic",
        "m_pagesnbind",
        "The Pragmatic Programmer",
        "20th anniversary edition, hardcover.",
        219_900,
    ),
    (
        "p_book_ddia",
        "m_pagesnbind",
        "Designing Data-Intensive Applications",
        "Kleppmann's classic on data systems.",
        249_900,
    ),
    (
        "p_book_gita",
        "m_pagesnbind",
        "Bhagavad Gita (Annotated)",
        "Translation with commentary, deluxe binding.",
        59_900,
    ),
    (
        "p_book_algorithms",
        "m_pagesnbind",
        "Grokking Algorithms",
        "Illustrated guide, second edition.",
        179_900,
    ),
    (
        "p_notebook_dot",
        "m_pagesnbind",
        "Dot-Grid Notebook A5",
        "180 GSM paper, lay-flat binding.",
        34_900,
    ),
    (
        "p_pen_fountain",
        "m_pagesnbind",
        "Brass Fountain Pen",
        "Fine nib, converter included.",
        109_900,
    ),
    (
        "p_bookends_iron",
        "m_pagesnbind",
        "Cast Iron Bookends",
        "Pair of minimalist L-bookends.",
        74_900,
    ),
    (
        "p_yogamat_pro",
        "m_fitkart",
        "Pro Yoga Mat 6mm",
        "Non-slip TPE, alignment lines.",
        119_900,
    ),
    (
        "p_dumbbells_10",
        "m_fitkart",
        "Hex Dumbbells 10kg Pair",
        "Rubber-coated cast iron.",
        219_900,
    ),
    (
        "p_resistance_set",
        "m_fitkart",
        "Resistance Bands Set",
        "5 bands, door anchor, handles.",
        89_900,
    ),
    (
        "p_shaker_700",
        "m_fitkart",
        "Steel Shaker 700ml",
        "Leak-proof, blender ball included.",
        44_900,
    ),
    (
        "p_skipping_rope",
        "m_fitkart",
        "Speed Skipping Rope",
        "Ball-bearing handles, adjustable cable.",
        29_900,
    ),
    (
        "p_cricket_bat",
        "m_fitkart",
        "Kashmir Willow Cricket Bat",
        "Full size, pre-knocked.",
        189_900,
    ),
    (
        "p_badminton_set",
        "m_fitkart",
        "Badminton Racket Set",
        "2 rackets, 3 shuttles, carry bag.",
        134_900,
    ),
    (
        "p_diffuser_ultra",
        "m_homely",
        "Ultrasonic Aroma Diffuser",
        "300ml, wood grain finish, auto shut-off.",
        94_900,
    ),
    (
        "p_bedsheet_king",
        "m_homely",
        "King Cotton Bedsheet Set",
        "400 TC sateen, 2 pillow covers.",
        169_900,
    ),
    (
        "p_lamp_terracotta",
        "m_homely",
        "Terracotta Table Lamp",
        "Handcrafted base, linen shade.",
        149_900,
    ),
    (
        "p_planter_set",
        "m_homely",
        "Ceramic Planter Set of 3",
        "Matte glaze, drainage holes.",
        84_900,
    ),
    (
        "p_wallclock_min",
        "m_homely",
        "Minimal Wall Clock 12in",
        "Silent sweep movement, oak frame.",
        74_900,
    ),
    (
        "p_curtains_black",
        "m_homely",
        "Blackout Curtains Pair",
        "7ft, thermal insulated, eyelet.",
        139_900,
    ),
]


def main() -> None:
    session = get_session_factory()()
    try:
        for mid, name, category in MERCHANTS:
            session.execute(
                insert(Merchant)
                .values(id=mid, name=name, category=category)
                .on_conflict_do_update(
                    index_elements=[Merchant.id], set_={"name": name, "category": category}
                )
            )
        for pid, mid, title, description, price in PRODUCTS:
            session.execute(
                insert(Product)
                .values(
                    id=pid,
                    merchant_id=mid,
                    title=title,
                    description=description,
                    price_paise=price,
                    currency="INR",
                )
                .on_conflict_do_update(
                    index_elements=[Product.id],
                    set_={"title": title, "description": description, "price_paise": price},
                )
            )
        session.commit()
        print(f"seeded {len(MERCHANTS)} merchants, {len(PRODUCTS)} products")
    finally:
        session.close()


if __name__ == "__main__":
    main()
