-- Fix month capitalisation in the expenses table
-- Run once on PythonAnywhere: sqlite3 /home/marcuslc/casetta.db < fix_month_capitalisation.sql

UPDATE expenses SET month = CASE UPPER(month)
    WHEN 'JAN' THEN 'Jan' WHEN 'FEB' THEN 'Feb' WHEN 'MAR' THEN 'Mar'
    WHEN 'APR' THEN 'Apr' WHEN 'MAY' THEN 'May' WHEN 'JUN' THEN 'Jun'
    WHEN 'JUL' THEN 'Jul' WHEN 'AUG' THEN 'Aug' WHEN 'SEP' THEN 'Sep'
    WHEN 'OCT' THEN 'Oct' WHEN 'NOV' THEN 'Nov' WHEN 'DEC' THEN 'Dec'
    ELSE month END
WHERE month != CASE UPPER(month)
    WHEN 'JAN' THEN 'Jan' WHEN 'FEB' THEN 'Feb' WHEN 'MAR' THEN 'Mar'
    WHEN 'APR' THEN 'Apr' WHEN 'MAY' THEN 'May' WHEN 'JUN' THEN 'Jun'
    WHEN 'JUL' THEN 'Jul' WHEN 'AUG' THEN 'Aug' WHEN 'SEP' THEN 'Sep'
    WHEN 'OCT' THEN 'Oct' WHEN 'NOV' THEN 'Nov' WHEN 'DEC' THEN 'Dec'
    ELSE month END;

SELECT 'Fixed ' || changes() || ' rows.' AS result;
