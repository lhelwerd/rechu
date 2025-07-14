"""
Subcommand to match entities in the database.
"""

from .base import Base
from ..database import Database
from ..matcher.product import ProductMatcher

@Base.register("match")
class Match(Base):
    """
    Update entities with references to metadata based on matching patterns.
    """

    subparser_keywords = {
        'help': 'Connect receipt product items to metadata',
        'description': 'Match products based on labels, prices and discounts '
                       'and connect the items to their product metadata.'
    }
    subparser_arguments = [
        (('-u', '--update'), {
            'action': 'store_true',
            'default': False,
            'help': 'Also update existing matched product references'
        })
    ]

    def __init__(self) -> None:
        super().__init__()
        self.update = False

    def run(self) -> None:
        with Database() as session:
            matcher = ProductMatcher()
            pairs = matcher.find_candidates(session,
                                            only_unmatched=not self.update)
            for product, item in matcher.filter_duplicate_candidates(pairs):
                self.logger.info('Matching %r with %r', item, product)
                item.product = product
