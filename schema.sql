CREATE TABLE IF NOT EXISTS days (
    day_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    creation_time INTEGER DEFAULT (datetime('now'))
);

CREATE UNIQUE INDEX IF NOT EXISTS days_id ON days(day_id);



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

    society_level INTEGER,
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

CREATE UNIQUE INDEX IF NOT EXISTS planet_info_id ON planet_info(info_id);



CREATE TABLE IF NOT EXISTS planet_budget (
    budget_id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    planet_id INTEGER,
    day_id INTEGER,

    income_tax INTEGER,

    trade_incentives INTEGER,
    fleet_upkeep INTEGER,
    matter_synth_1 INTEGER,
    matter_synth_2 INTEGER,
    long_range_sensors_1 INTEGER,
    long_range_sensors_2 INTEGER,
    military_base INTEGER,
    slingshot INTEGER,
    regional_government INTEGER,
    mind_control INTEGER,

    total_credits INTEGER,
    total_debits INTEGER,
    budget_surplus INTEGER
);

CREATE UNIQUE INDEX IF NOT EXISTS planet_budget_id ON planet_budget(budget_id);



DROP VIEW IF EXISTS current_day;
CREATE VIEW current_day AS
SELECT d.day_id, d.creation_time
  FROM days d
 ORDER BY d.creation_time DESC LIMIT 1
;

DROP VIEW IF EXISTS open_trading_planets;
CREATE VIEW open_trading_planets AS
SELECT p.name, p.planet_id, i.society_level
  FROM planets p JOIN planet_info i
    ON p.planet_id=i.planet_id
 WHERE open_trading='yes'
   AND day_id = (SELECT day_id FROM current_day);
;

DROP VIEW IF EXISTS planet_resources;
CREATE VIEW planet_resources AS
SELECT p.name, p.planet_id, day_id,
       steel_on_hand as steel,
       unobtanium_on_hand as unobtanium,
       food_on_hand as food,
       antimatter_on_hand as antimatter,
       krellmetal_on_hand as krellmetal,
       population as people,
       treasury as quatloos
  FROM planets p JOIN planet_info i
    ON p.planet_id=i.planet_id
;

DROP VIEW IF EXISTS planet_prices;
CREATE VIEW planet_prices AS
SELECT p.name, p.planet_id, day_id,
       steel_price as steel,
       unobtanium_price as unobtanium,
       food_price as food,
       antimatter_price as antimatter,
       krellmetal_price as krellmetal,
       hydrocarbon_price as hydrocarbon,
       consumergoods_price as consumergoods
  FROM planets p JOIN planet_info i
    ON p.planet_id=i.planet_id
;

DROP VIEW IF EXISTS current_resources;
CREATE VIEW current_resources AS
SELECT *
  FROM planet_resources
 WHERE day_id = (SELECT day_id FROM current_day)
;

DROP VIEW IF EXISTS current_prices;
CREATE VIEW current_prices AS
SELECT *
  FROM planet_prices
 WHERE day_id = (SELECT day_id FROM current_day)
;

DROP VIEW IF EXISTS arc_builders;
CREATE VIEW arc_builders AS
SELECT p.name, p.planet_id, b.fleet_upkeep, b.budget_surplus
  FROM planets p, current_resources r, planet_budget b
 WHERE p.planet_id=b.planet_id AND p.planet_id=r.planet_id
   AND day_id = (SELECT day_id FROM current_day)
   AND r.steel > 200
   AND r.food > 1000
   AND r.people > 200
   AND r.antimatter > 10
   AND r.quatloos > 200
;

DROP VIEW IF EXISTS new_planets;
CREATE VIEW new_planets AS
SELECT p.name, p.planet_id, i.society_level
  FROM planets p JOIN planet_info i
    ON p.planet_id=i.planet_id
 WHERE date(p.creation_time) = 
       (SELECT date(d.creation_time) FROM current_day d);

