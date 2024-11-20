def bot_messages(bot_secrets, bot_number):
    from typing import List
    import FunPayAPI
    import logging
    import gc
    from time import sleep
    logger = logging.getLogger(bot_secrets.__name__ + "_messages")
    bot_secrets.auto_reply = {k.lower(): v for k, v in bot_secrets.auto_reply.items()}

    try:
        path_to_images = './images/images'
        delay = 2

        try:
            acc = FunPayAPI.Account(bot_secrets.golden_key).get()
        except FunPayAPI.common.exceptions.UnauthorizedError as e:
            logger.critical("Похоже golden_key просочен. Бот работать не может! Обнови golden_key и перезапусти бота")
            sleep(60 * 5)
            exit(1)
        logger.info(f"FunPayAPI.Account {acc.username} loaded")
        runner = FunPayAPI.Runner(acc)

        def new_messages_handler(events: List[FunPayAPI.events.BaseEvent]):
            new_message_events: List[FunPayAPI.common.enums.EventTypes.NEW_MESSAGE] = \
                [event for event in events if event.type == FunPayAPI.common.enums.EventTypes.NEW_MESSAGE]
            for event in new_message_events:
                for trigger, message in bot_secrets.auto_reply.items():
                    if type(event.message.text) == str:
                        if trigger in event.message.text.lower() and event.message.author != acc.username:
                            if type(message) == str:
                                acc.send_message(event.message.chat_id, message)
                                logger.info(f'Send {trigger} to {event.message.chat_id}')
                                break
                            elif type(message) == list or type(message) == tuple:
                                for mes in message:
                                    try:
                                        if mes[0] != '/':
                                            acc.send_message(event.message.chat_id, mes)
                                        else:
                                            acc.send_image(event.message.chat_id, path_to_images + mes)
                                    except Exception as e:
                                        logger.error(f'Error on send {trigger} to {event.message.chat_id}',
                                                     exc_info=True)
                                logger.info(f'Send {trigger} to {event.message.chat_id}')
                                break

        def main():
            for events in runner.listen(requests_delay=delay):
                logger.debug("Cycle starts")

                new_messages_handler(events)

                gc.collect()

        main()

    except Exception as exception:
        logger.critical(exception, exc_info=True)
        exit(1)


if __name__ == '__main__':
    import importlib

    bot_messages(importlib.import_module("bot_secrets.A0EDAVA1KA"), 0)
