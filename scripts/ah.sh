#!/bin/bash

# Some tests with crawling AH GraphQL API

curl -H 'Accept: */*' -H 'User-Agent: Mozilla/5.0 (Linux x86_64; rv:130.0) Gecko/20100101 Firefox/130.0' -H 'batch: true' -H 'Content-Type: application/json' --data '{"query":"query getProduct {\n product(id:3184){\n title\n brand\n category\n webPath\n summary\n salesUnitSize\n tradeItem {\n gtin\n gtinRevisions\n description {\n descriptions\n definitions\n }\n ingredients {\n statement\n }\n nutritions {\n nutrients {\n type\n name\n value\n }\n basisQuantity\n }\n contents {\n netContents\n servingsPerPackage\n }\n }\n taxonomies {\n name\n id\n slug\n parents\n }\n }\n }"}' -H 'x-client-name: ah-products' -H 'x-client-platform-type: Web' -H 'x-client-version: 6.608.59' -H 'Referer: https://www.ah.nl/producten/product/wi225108/caramel-en-creme' -H 'Origin: https://www.ah.nl' -H 'Priority: u=4' -H 'Sec-Fetch-Dest: empty' -H 'Sec-Fetch-Mode: cors' -H 'Sec-Fetch-Site: same-origin' --compressed --output - https://www.ah.nl/gql
