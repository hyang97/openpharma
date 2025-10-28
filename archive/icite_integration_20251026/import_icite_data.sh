#!/bin/bash
# One-time import of iCite data into Postgres using COPY command

set -e  # Exit on error

echo "Starting iCite data import..."
echo ""

# Import metadata (~27GB, ~40M rows, ~2-4 hours)
echo "Importing icite_metadata.csv..."
cat data/icite_2025_09/icite_metadata.csv | docker-compose exec -T postgres psql -U admin -d openpharma -c "COPY icite_metadata FROM STDIN WITH (FORMAT csv, HEADER true);"
echo "✓ Metadata import complete"
echo ""

# Import citation links (~14GB, ~500M rows, ~3-5 hours)
echo "Importing open_citation_collection.csv..."
cat data/icite_2025_09/open_citation_collection.csv | docker-compose exec -T postgres psql -U admin -d openpharma -c "COPY citation_links FROM STDIN WITH (FORMAT csv, HEADER true, DELIMITER ',');"
echo "✓ Citation links import complete"
echo ""

# Create indexes (~30-60 minutes)
echo "Creating indexes..."
docker-compose exec -T postgres psql -U admin -d openpharma -c "CREATE INDEX idx_icite_percentile ON icite_metadata(nih_percentile);"
echo "  ✓ idx_icite_percentile"
docker-compose exec -T postgres psql -U admin -d openpharma -c "CREATE INDEX idx_icite_year ON icite_metadata(year);"
echo "  ✓ idx_icite_year"
docker-compose exec -T postgres psql -U admin -d openpharma -c "CREATE INDEX idx_icite_citation_count ON icite_metadata(citation_count);"
echo "  ✓ idx_icite_citation_count"
docker-compose exec -T postgres psql -U admin -d openpharma -c "CREATE INDEX idx_citation_links_citing ON citation_links(citing);"
echo "  ✓ idx_citation_links_citing"
docker-compose exec -T postgres psql -U admin -d openpharma -c "CREATE INDEX idx_citation_links_cited ON citation_links(referenced);"
echo "  ✓ idx_citation_links_cited"
echo ""

echo "✓ All done!"
