def bot(bot_secrets, bot_number):
    from typing import List
    import datetime
    import re
    import FunPayAPI
    from gspread_pandas import conf
    from my_spread import MySpread as Spread
    import pandas as pd
    from urllib.parse import urlparse, parse_qs
    import logging
    import gc
    from time import sleep
    logger = logging.getLogger(bot_secrets.__name__)

    try:
        conf._default_dir = "./bot_secrets"
        lot_type_finder = re.compile(", Аренда|, Продажа")
        delay = 5
        accounts_amount_in_lot = 20

        acc = FunPayAPI.Account(bot_secrets.golden_key).get()
        logger.info(f"FunPayAPI.Account {acc.username} loaded")
        runner = FunPayAPI.Runner(acc)
        spread = Spread(bot_secrets.sheet_url)
        logger.info("Spread loaded")

        def get_accounts_df() -> pd.DataFrame:
            nonlocal spread

            def whitespace_remover(dataframe):
                for i in dataframe.columns:
                    if dataframe[i].dtype == 'object':
                        dataframe[i] = dataframe[i].map(str.strip)
                    else:
                        pass

            def get_index(url):
                parsed_url = parse_qs(urlparse(url).query)
                if 'offer' in parsed_url:
                    return int(parsed_url['offer'][0])
                else:
                    return None

            df_got = False
            df = None
            while not df_got:
                try:
                    df = spread.sheet_to_df(sheet=bot_secrets.accounts_sheet_name, index=0)
                    df_got = True
                except Exception as e:
                    logger.warning('Error getting DataFrame', exc_info=e)
                    spread = Spread(bot_secrets.sheet_url)
            df = df[bot_secrets.columns_names.keys()].rename(columns=bot_secrets.columns_names)
            df.index = df["url"].apply(get_index).astype(float).rename("id")
            whitespace_remover(df)
            logger.debug("get_accounts_df")
            return df

        def save_accounts_df(df: pd.DataFrame, df_original: pd.DataFrame):
            df[df == df_original] = None
            df = df.rename(columns={v: k for k, v in bot_secrets.columns_names.items()})
            spread.df_to_sheet(df, sheet=bot_secrets.accounts_sheet_name, start="A1", index=False)
            logger.debug("Sheet saved")

        def get_active_lots_df() -> pd.DataFrame:
            lots = [{'id': lot.id, 'name': lot.title[:lot_type_finder.search(lot.title).start()], 'title': lot.title}
                    for lot in acc.get_user(acc.id).get_lots() if lot.subcategory.id == bot_secrets.subcategory_id]
            return pd.DataFrame(lots).set_index('id')

        def new_orders_handler(events: List[FunPayAPI.events.BaseEvent], accounts_df: pd.DataFrame):
            new_orders_events = [event for event in events if event.type == FunPayAPI.common.enums.EventTypes.NEW_ORDER]
            if new_orders_events:
                try:
                    lots_df = get_active_lots_df()
                    accounts_df_with_names = lots_df.join(accounts_df, how='inner')
                    for event in new_orders_events:
                        try:
                            order_shortcut: FunPayAPI.types.OrderShortcut = event.order
                            order = acc.get_order(order_shortcut.id)
                            lots = accounts_df_with_names.loc[accounts_df_with_names['name'] == order.title]
                            if len(lots) != 1:
                                logger.error(f'Found {len(lots)} accounts {order.title}')
                                if len(lots) == 0:
                                    continue
                            account = lots.iloc[0]
                            lot = acc.get_lot_fields(account.name)
                            lot.active = False
                            accounts_df.loc[account.name, 'rent_start'] = order_shortcut.date.strftime('%Y/%m/%d %H:%M')
                            accounts_df.loc[account.name, 'rent_finish'] = (order_shortcut.date + datetime.timedelta(
                                hours=order_shortcut.amount)).strftime('%Y/%m/%d %H:%M')
                            acc_saved = False
                            while not acc_saved:
                                try:
                                    acc.save_lot(lot)
                                    acc_saved = True
                                except Exception as e:
                                    logger.warning(f'Error saving lot {lot.title_ru} when purchasing. {e}')
                                    sleep(2)
                            logger.info(f"{lot.title_ru} is deactivated")
                        except Exception as e:
                            logger.error(e, exc_info=True)
                except Exception as e:
                    logger.error(e, exc_info=True)

        def update_lots_handler(accounts_df: pd.DataFrame, original_df: pd.DataFrame):
            for name, account in accounts_df.loc[(accounts_df['rent_start'] == '') &
                                                 (accounts_df['funpay_account'] == bot_secrets.funpay_account) &
                                                 ((accounts_df != original_df).any(axis=1))].iterrows():
                try:
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
                    acc_saved = 5
                    while acc_saved > 0:
                        try:
                            acc.save_lot(lot)
                            acc_saved = -1
                        except Exception as e:
                            logger.warning(f'Error saving lot {lot.title_ru} when updating. {e}')
                            acc_saved -= 1
                            sleep(2)
                    if acc_saved == -1:
                        logger.info(f"{lot.title_ru} is updated")
                except Exception as e:
                    logger.error(e, exc_info=True)

        def main():
            accounts_df_original = get_accounts_df()
            for events in runner.listen(requests_delay=delay, disable_chat=True):
                logger.debug("Cycle starts")
                accounts_df = get_accounts_df()

                update_lots_handler(accounts_df, accounts_df_original)

                accounts_df_original = accounts_df.copy()

                new_orders_handler(events, accounts_df)

                save_accounts_df(accounts_df, accounts_df_original)
                del accounts_df
                gc.collect()

        main()

    except Exception as exception:
        logger.critical(exception, exc_info=True)
        exit(1)


if __name__ == '__main__':
    import importlib

    bot(importlib.import_module("bot_secrets.A0EDAVA1KA"), 0)
