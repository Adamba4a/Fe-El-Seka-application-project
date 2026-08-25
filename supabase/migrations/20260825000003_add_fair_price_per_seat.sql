ALTER TABLE rides
    ADD COLUMN fair_price_per_seat NUMERIC(10,2);

UPDATE rides
    SET fair_price_per_seat = price_per_seat
    WHERE fair_price_per_seat IS NULL;

ALTER TABLE rides
    ALTER COLUMN fair_price_per_seat SET NOT NULL;
