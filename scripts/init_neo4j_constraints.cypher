// Neo4j Constraints for Predator Analytics v13
// Ensures unique keys for Company, Product, Country nodes
// Run once during initial setup or after schema changes

// Company uniqueness by EDRPOU
CREATE CONSTRAINT company_edrpou_unique IF NOT EXISTS
FOR (c:Company) REQUIRE c.edrpou IS UNIQUE;

// Product uniqueness by HS code
CREATE CONSTRAINT product_hs_code_unique IF NOT EXISTS
FOR (p:Product) REQUIRE p.hs_code IS UNIQUE;

// Country uniqueness by ISO code
CREATE CONSTRAINT country_code_unique IF NOT EXISTS
FOR (co:Country) REQUIRE co.code IS UNIQUE;

// Optional: Add indexes for performance
CREATE INDEX company_name_index IF NOT EXISTS FOR (c:Company) ON (c.name);
CREATE INDEX product_hs_code_index IF NOT EXISTS FOR (p:Product) ON (p.hs_code);
CREATE INDEX country_code_index IF NOT EXISTS FOR (co:Country) ON (co.code);
