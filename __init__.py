# The COPYRIGHT file at the top level of this repository contains the full
# copyright notices and license terms.
from trytond.pool import Pool
from .sale import *


def register():
    Pool.register(
        Sale,
        RecomputePriceStart,
        module='sale_recompute_price', type_='model')
    Pool.register(
        RecomputePrice,
        module='sale_recompute_price', type_='wizard')
