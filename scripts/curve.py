from brownie import *
import time
import requests
from prometheus_client import start_http_server, Gauge


pool_info = {
    'compound': {
        'swap': '0xA2B47E3D5c44877cca798226B7B8118F9BFb7A56',
        'swap_token': '0x845838DF265Dcd2c412A1Dc9e959c7d08537f8a2',
        'gauge': '0x7ca5b0a2910B33e9759DC7dDB0413949071D7575',
    },
    'usdt': {
        'swap': '0x52EA46506B9CC5Ef470C5bf89f17Dc28bB35D85C',
        'swap_token': '0x9fC689CCaDa600B6DF723D9E47D84d76664a1F23',
        'gauge': '0xBC89cd85491d81C6AD2954E6d0362Ee29fCa8F53',
    },
    'y': {
        'swap': '0x45F783CCE6B7FF23B2ab2D70e416cdb7D6055f51',
        'swap_token': '0xdF5e0e81Dff6FAF3A7e52BA697820c5e32D806A8',
        'gauge': '0xFA712EE4788C042e2B7BB55E6cb8ec569C4530c1',
    },
    'busd': {
        'swap': '0x79a8C46DeA5aDa233ABaFFD40F3A0A2B1e5A4F27',
        'swap_token': '0x3B3Ac5386837Dc563660FB6a0937DFAa5924333B',
        'gauge': '0x69Fb7c45726cfE2baDeE8317005d3F94bE838840',
    },
    'susdv2': {
        'swap': '0xA5407eAE9Ba41422680e2e00537571bcC53efBfD',
        'swap_token': '0xC25a3A3b969415c80451098fa907EC722572917F',
        'gauge': '0xA90996896660DEcC6E997655E065b23788857849',
    },
    'pax': {
        'swap': '0x06364f10B501e868329afBc005b3492902d6C763',
        'swap_token': '0xD905e2eaeBe188fc92179b6350807D8bd91Db0D8',
        'gauge': '0x64E3C23bfc40722d3B649844055F1D51c1ac041d',
    },
    'ren': {
        'swap': '0x93054188d876f558f4a66B2EF1d97d16eDf0895B',
        'swap_token': '0x49849C98ae39Fff122806C06791Fa73784FB3675',
        'gauge': '0xB1F2cdeC61db658F091671F5f199635aEF202CAC',
    },
    'sbtc': {
        'swap': '0x7fC77b5c7614E1533320Ea6DDc2Eb61fa00A9714',
        'swap_token': '0x075b1bb99792c9E1041bA13afEf80C91a1e70fB3',
        'gauge': '0x705350c4BcD35c9441419DdD5d2f097d7a55410F',
    },
}

crv = interface.CurveToken('0xD533a949740bb3306d119CC777fa900bA034cd52')
crv_lp_vesting = interface.CurveVesting('0x575CCD8e2D300e2377B43478339E364000318E2c')
crv_gauge_controller = interface.CurveGaugeController('0x2F50D538606Fa9EDD2B11E2446BEb18C9D5846bB')

contracts = {
    'gauge': {name: interface.CurveGauge(pool_info[name]['gauge']) for name in pool_info},
    'swap': {name: interface.CurveSwap(pool_info[name]['swap']) for name in pool_info},
    'lp_token': {name: interface.CurveSwapToken(pool_info[name]['swap_token']) for name in pool_info},
}

# prometheus gauges
crv_balance = Gauge('crv_balance', '', ['address'])
crv_vested = Gauge('crv_vested', '', ['address'])
crv_gauge_claimable = Gauge('crv_gauge_claimable', '', ['address', 'gauge'])
crv_gauge_balance = Gauge('crv_gauge_balance', '', ['address', 'gauge'])
crv_gauge_inflation_rate = Gauge('crv_gauge_inflation_rate', '', ['gauge'])
crv_gauge_virtual_price = Gauge('crv_gauge_virtual_price', '', ['gauge'])
crv_gauge_working_supply = Gauge('crv_gauge_working_supply', '', ['gauge'])
crv_gauge_total_supply = Gauge('crv_gauge_total_supply', '', ['gauge'])
crv_gauge_period = Gauge('crv_gauge_period', '', ['gauge'])
crv_gauge_relative_weight = Gauge('crv_gauge_relative_weight', '', ['gauge'])
crv_gauge_rate = Gauge('crv_gauge_rate', '', ['gauge'])
crv_gauge_apy = Gauge('crv_gauge_apy', '', ['gauge'])
coingecko_price = Gauge('coingecko_price', '', ['asset'])


def main():
    port = 8779
    start_http_server(port)
    print(f'listenting on :{port}')
    while True:
        prices = requests.get('https://api.coingecko.com/api/v3/simple/price', params={'ids': 'bitcoin,curve-dao-token', 'vs_currencies': 'usd'}).json()
        btc_price = prices['bitcoin']['usd']
        crv_price = prices['curve-dao-token']['usd']

        coingecko_price.labels('btc').set(btc_price)
        coingecko_price.labels('crv').set(crv_price)

        for name in pool_info:
            gauge = contracts['gauge'][name]
            swap = contracts['swap'][name]
            relative_weight = crv_gauge_controller.gauge_relative_weight(gauge) / 1e18
            inflation_rate = gauge.inflation_rate() / 1e18
            virtual_price = swap.get_virtual_price() / 1e18
            working_supply = gauge.working_supply() / 1e18
            if name in ['ren', 'sbtc']:
                working_supply *= btc_price
            try:
                rate = (inflation_rate * relative_weight * 31536000 / working_supply * 0.4) / virtual_price
                apy = rate * crv_price * 100
            except ZeroDivisionError:
                rate = 0
                apy = 0

            crv_gauge_relative_weight.labels(name).set(relative_weight)
            crv_gauge_inflation_rate.labels(name).set(inflation_rate)
            crv_gauge_working_supply.labels(name).set(working_supply)
            crv_gauge_total_supply.labels(name).set(gauge.totalSupply() / 1e18)
            crv_gauge_virtual_price.labels(name).set(virtual_price)
            crv_gauge_period.labels(name).set(gauge.period())
            crv_gauge_rate.labels(name).set(rate)
            crv_gauge_apy.labels(name).set(apy)

        time.sleep(60)


if __name__ == '__main__':
    main()
