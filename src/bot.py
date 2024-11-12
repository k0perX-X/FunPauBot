def bot(bot_secrets, bot_number):
    from typing import List
    import datetime
    import re
    import FunPayAPI
    from gspread_pandas import Spread, conf
    import pandas as pd
    from urllib.parse import urlparse, parse_qs
    import numpy as np
    import logging
    logger = logging.getLogger(bot_secrets.__name__)

    conf._default_dir = "./bot_secrets"
    lot_type_finder = re.compile(", Аренда|, Продажа")
    delay = 60
    accounts_amount_in_lot = 20

    acc = FunPayAPI.Account(bot_secrets.golden_key).get()
    logger.info(f"FunPayAPI.Account loaded")
    runner = FunPayAPI.Runner(acc)
    spread = Spread(bot_secrets.sheet_url)
    logger.info("Spread loaded")

    def get_accounts_df() -> pd.DataFrame:
        def whitespace_remover(dataframe):
            for i in dataframe.columns:
                if dataframe[i].dtype == 'object':
                    dataframe[i] = dataframe[i].map(str.strip)
                else:
                    pass

        df = spread.sheet_to_df(sheet=bot_secrets.accounts_sheet_name, start_row=1, index=0)[
            bot_secrets.columns_names.keys()].rename(
            columns=bot_secrets.columns_names)
        df = df.loc[df['funpay_account'] == bot_secrets.funpay_account]
        df.index = df["url"].apply(lambda x: int(parse_qs(urlparse(x).query)['offer'][0])).rename("id")
        whitespace_remover(df)
        df.replace('', np.nan, inplace=True)
        df['rent_start'] = pd.to_datetime(df['rent_start'])
        df['rent_finish'] = pd.to_datetime(df['rent_finish'])
        logger.debug("get_accounts_df")
        return df

    def save_accounts_df(df: pd.DataFrame):
        new_df = df.copy()
        new_df['rent_start'] = new_df['rent_start'].dt.strftime('%Y/%m/%d %H:%M')
        new_df['rent_finish'] = new_df['rent_finish'].dt.strftime('%Y/%m/%d %H:%M')
        new_df = new_df.rename(columns={v: k for k, v in bot_secrets.columns_names.items()})
        spread.df_to_sheet(new_df, sheet=bot_secrets.accounts_sheet_name, start="A1", index=False)
        logger.debug("save_accounts_df")

    def get_active_lots_df() -> pd.DataFrame:
        lots = [{'id': lot.id, 'name': lot.title[:lot_type_finder.search(lot.title).start()], 'title': lot.title}
                for lot in acc.get_user(acc.id).get_lots() if lot.subcategory.id == bot_secrets.subcategory_id]
        return pd.DataFrame(lots).set_index('id')

    def new_orders_handler(events: List[FunPayAPI.events.BaseEvent], accounts_df: pd.DataFrame):
        new_orders_events = [event for event in events if event.type == FunPayAPI.common.enums.EventTypes.NEW_ORDER]
        if new_orders_events:
            lots_df = get_active_lots_df()
            accounts_df_with_names = lots_df.join(accounts_df, how='inner')
            for event in new_orders_events:
                order_shortcut: FunPayAPI.types.OrderShortcut = event.order
                order = acc.get_order(order_shortcut.id)
                lots = accounts_df_with_names.loc[accounts_df_with_names['name'] == order.title]
                if len(lots) != 1:
                    logger.error(f'Найдено {len(lots)} аккаунтов {order.title}')
                    if len(lots) == 0:
                        continue
                account = lots.iloc[0]
                lot = acc.get_lot_fields(account.name)
                lot.active = False
                accounts_df.loc[account.name, 'rent_start'] = order_shortcut.date
                accounts_df.loc[account.name, 'rent_finish'] = order_shortcut.date + datetime.timedelta(
                    hours=order_shortcut.amount)
                acc.save_lot(lot)
                logger.info(f"{lot.title_ru} is deactivated")

    def update_lots_handler(accounts_df: pd.DataFrame):
        for name, account in accounts_df.loc[pd.isna(accounts_df['rent_start'])].iterrows():
            lot = acc.get_lot_fields(name)
            lot.active = True
            lot.edit_fields({
                'fields[solommr]': str(account['solommr']),
                'fields[decency]': str(account['decency']),
                'secrets': f'{account["login"]} {account["password"]} \n' * accounts_amount_in_lot,
            })
            lot.amount = accounts_amount_in_lot
            lot.price = account['price']
            lot.renew_fields()
            acc.save_lot(lot)

    for events in runner.listen(requests_delay=delay):
        accounts_df = get_accounts_df()

        new_orders_handler(events, accounts_df)
        update_lots_handler(accounts_df)

        save_accounts_df(accounts_df)


if __name__ == '__main__':
    import importlib

    bot(importlib.import_module("bot_secrets.A0EDAVA1KA"), 0)
