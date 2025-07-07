# Input files

As mentioned in the [commands reference](commands.md), there are two methods of 
filling the receipt cataloging database with receipts and product information. 
One method is to interactively create 
[new](commands.md#new-receipts-and-products) receipts and products, which also 
writes YAML files for later changes and synchronization. The second method is 
to create such YAML files from scratch and import them by [reading them 
in](commands.md#read-files).

The receipt and product files follow a specific structure which allows them to 
be read in programmatically while still being fairly readable and succinct. The 
files are also meant to be more portable compared to a PostgreSQL database, for 
example, and the I/O tools of the module remain compatible with format changes 
as they are introduced, whereas [database 
migrations](commands.md#alembic-migration) are somewhat more tedious.

For validation and other automation purposes, [JSON schemas](schemas.rst) exist 
to describe the YAML structure, but this is less useful for human consumption. 
Therefore, we also provide a number of example files for the receipt and 
product metadata files.

:::{tip}
Remember that the files are meant to be stored relative to the data path and 
within the subdirectories discovered with the pattern configured in the 
[settings](configuration.md), so any mentions of filenames here are relative to 
those paths.
:::

## Receipts

The receipt YAML file contains a single receipt's metadata, such as date of the 
receipt and the shop it is from, as well as the products and discounts. The 
following `receipt.yml` file shows an example receipt with some dummy data:

```{literalinclude} ../../samples/receipt.yml
```

Follow year-month-day (YMD) conventions for writing the date. The shop should 
be a simple identifier that is repeated for all receipts of that shop. The 
products are entries of a list, with each product a list of three or four 
elements. In order, the product has the following fields:

- The quantity of the product, either as a plain, exact number or as 
  a (fractional) number with a unit (such as kilograms), if the product is 
  weighed at purchase, for example.
- The label of the product, as it appears on the receipt. The convention is to 
  use lowercase labels, but this is up to you to choose, although it is a good 
  idea to write the label the same way when it appears on different receipts.
- The price of the product, multiplied by the quantity. This should not just be 
  the price of a singular product or the "unit price", because this field is 
  also used as-is for total price calculation of a receipt. However, discounts 
  (if those are listed separately) should not be deducted from this price, to 
  make price tracking across time and base price matching in product metadata 
  feasible.
- An indicator that the product received a separate discount. If the receipt 
  has a particular character (or short set of characters) for this, then that 
  is a good option to use, otherwise this should include something if the 
  product is involved in such a discount. The indicator itself is not relevant.

For discounts, which are stored in a `bonus` entry, we also have an array with 
lists with at least two entries:

- The label of the discount as it appears on the receipt.
- The decrease in price that the discount provided across all the products 
  involved in the sale.
- Any further elements refer to labels defined in the `products` entry. These 
  should be listed in order of appearance and not refer to any products that 
  are not involved in any discount. If multiple products have the same label, 
  the order should in most case make it clear which product is involved; if 
  somehow an earlier product is not involved in this discount but a later one, 
  then mismatches may occur, so consider adjusting labels then. If additional 
  granularity is needed on how the discount is broken down over products, then 
  consider splitting up a discount.

In the example above, there are six products with one having a quantity with 
a unit. Three products have the same label, but only two of them had a discount 
(which the bonus section refers to by their label in order). The final product 
also has a discount with a different indicator. The bonus section contains two 
discounts that refer to no product or a nonexistent product, respectively, but 
the discounts themselves still apply.

## Product inventories

Aside from primary receipt information, it is possible to augment product data 
with more metadata that help describe, group, shape and identify the items. 
Similarly to receipt files, product metadata is specified in YAML files.

By default, the convention is to have one YAML file for products from the same 
shop. However, by adjusting the products format in the data settings, you can 
also group together products with the same brand, category and/or type, on top 
of the shop. These YAML files are also called *inventories*, and an example of 
a file, `products-id.yml`, is shown below.

```{literalinclude} ../../samples/products-id.yml
```

The YAML file has a shop identifier, possibly any other shared fields (the 
brand, category or type already mentioned), and the products that have metadata 
defined for each of them in a list. In order to match the metadata with receipt 
product items, we use *matchers*:

- For labels, we match a product's label with any of the names in the list.
- For prices, we either match a product's normalized price (i.e., after 
  dividing the value by the quantity, but without discounts) with one of the 
  prices in the list. Otherwise, the matchers for prices is an object with 
  keys, which could define a range using minimum and maximum prices (again 
  using the normalized price to compare with both interval ends required), 
  prices per year key (with a similar comparison) or prices for a particular 
  unit (using the normalized format for units as keys, such as 'kilogram' and 
  not 'kg').
- For discounts, we match the labels of any of the discounts that a product is 
  involved in (so not the discount indicator provided directly with the item) 
  with any of the names in the list.

Any of the matchers may be used to limit which item are considered to be the 
described product. Combinations of matches further restrict the match, which is 
important as matches with multiple top-level products lead to the items not 
being matched at all to any metadata. We later mention how to group an 
assortment of similar products together in a range with a generic product.

With the receipt and inventory examples above, the "weigh" product matches the 
fifth item on the receipt, which the "due" product matches the last item 
because the price of 0.89 is considered in the open interval. The third product 
(disregarding the range of products below it for now) matches the second and 
fourth item because they are involved in the "disco" discount and their 
normalized prices are 2.50 and 2.00, respectively.

For metadata, it is possible to define a product's brand, description, category 
and type, as text. This is free-form, although it is a good idea to write 
brands, categories and types in the same way, as a form of taxonomy across 
products. Additionally, we recognize the following numerical properties of 
products:

- The portions in a product, as a number. Use common sense whether this is 
  relevant to provide for you; normally this is the number of discrete items in 
  the package, but for other products this is a recommended serving size.
- The weight of a product, using a quantity with a unit.
- The volume of a product, using a quantity with a unit.
- The percentage of alcohol contained in a product.

There are also two identifiers recognized for the products, which are the `sku` 
(stock-keeping unit) and the `gtin` (global trade item number). The former may 
be obtained from an external registry of the shop for lookup purposes and is 
free-form text, while the latter is a number of at most 14 digits, which may
correspond to the barcode on a product, usually written with zeroes on the 
start of the number to pad it to the maximum length. These two identification 
codes should also be unique within the inventory (and the GTIN even across 
shops), meaning that the `rechu new` command detects duplicates and gives the 
option to merge them.

When a product comes in different forms which share the same properties or are 
otherwise hard to distinguish (like when they show up with the same labels, 
prices and/or discounts on the receipts), it is possible to define a range of 
product metadata items in an array. These inherit most fields from the generic 
product defined at the top level, except for sku/gtin identification codes. 
Product range metadata can override fields from the generic product and even 
leave out matchers, such as in the Small variant of the chocolate type product.

The matching algorithm prefers generic products over product range metadata 
when they have the same matchers, but with adjustments to their matchers, the 
metadata with the most narrow matchers prevails. This means that overriding 
a matcher to remove it completely decreases the specificity of that product 
(actually making it less likely to be used if it has a duplicate match), while 
overriding it to decrease the number of matching values increases its 
specificity. This is how the second and fourth product on the example receipt 
will end up matching the second and first range product, respectively.
