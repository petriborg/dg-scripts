CREATE TABLE IF NOT EXISTS days (
    day_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    creation_time INTEGER DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS days_id on days(day_id);



CREATE TABLE IF NOT EXISTS raw_pages (
    page_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    day_id INTEGER,
    url TEXT,
    page TEXT
);

CREATE UNIQUE INDEX IF NOT EXISTS raw_pages_id ON raw_pages(page_id);



CREATE TABLE IF NOT EXISTS planets (
    planet_id INTEGER PRIMARY KEY NOT NULL,
    name TEXT,
    creation_time INTEGER DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS planets_id ON planets(planet_id);



CREATE TABLE IF NOT EXISTS planet_info (
    info_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    planet_id INTEGER,
    day_id INTEGER,

    income_tax_rate REAL,
    tariff_rate REAL,
    open_ship_yard BOOLEAN,
    open_trading BOOLEAN,
    trades_rare_commodities BOOLEAN,
    population INTEGER,
    treasury INTEGER,

    steel_on_hand INTEGER,
    steel_next_production INTEGER,
    steel_price INTEGER,

    unobtanium_on_hand INTEGER,
    unobtanium_next_production INTEGER,
    unobtanium_price INTEGER,

    food_on_hand INTEGER,
    food_next_production INTEGER,
    food_price INTEGER,

    antimatter_on_hand INTEGER,
    antimatter_next_production INTEGER,
    antimatter_price INTEGER,

    consumergoods_on_hand INTEGER,
    consumergoods_next_production INTEGER,
    consumergoods_price INTEGER,

    hydrocarbon_on_hand INTEGER,
    hydrocarbon_next_production INTEGER,
    hydrocarbon_price INTEGER,

    krellmetal_on_hand INTEGER,
    krellmetal_next_production INTEGER,
    krellmetal_price INTEGER,

    UNIQUE (planet_id, day_id) ON CONFLICT IGNORE
);

CREATE UNIQUE INDEX IF NOT EXISTS planet_info_id on planet_info(info_id);


