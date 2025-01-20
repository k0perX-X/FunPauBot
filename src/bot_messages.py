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
        delay = 10

        try:
            acc = FunPayAPI.Account(bot_secrets.golden_key).get()
        except FunPayAPI.common.exceptions.UnauthorizedError as e:
            logger.critical("Похоже golden_key просочен. Бот работать не может! Обнови golden_key и перезапусти бота")
            sleep(60 * 5)
            exit(1)
        logger.info(f"FunPayAPI.Account {acc.username} loaded")
        runner = FunPayAPI.Runner(acc)

        def new_messages_handler(events: List[FunPayAPI.events.BaseEvent]):
            new_message_events: List[FunPayAPI.events.NewMessageEvent] = \
                [event for event in events if event.type == FunPayAPI.common.enums.EventTypes.NEW_MESSAGE]
            for event in new_message_events:
                messages = get_messages_from_chat(event.message)
                if messages:
                    if (not any([m.badge for m in messages]) and not any([m.by_bot for m in messages])
                            and all([m.get_message_type() == FunPayAPI.enums.MessageTypes.NON_SYSTEM for m in messages])
                            and all([m.author != acc.username for m in messages])):
                        try:
                            runner.chats[event.message.chat_id].append(
                                acc.send_message(event.message.chat_id, bot_secrets.welcome_message))
                            logger.info(f'Send welcome message to {event.message.author}')
                        except Exception as e:
                            logger.error(
                                f'Error on send welcome message to {event.message.author}',
                                exc_info=True)
                        break
                for trigger, message in bot_secrets.auto_reply.items():
                    if event.message.text != 'Изображение':
                        if (trigger in event.message.text.lower() and not event.message.badge
                                and event.message.get_message_type() == FunPayAPI.enums.MessageTypes.NON_SYSTEM
                                and event.message.author != acc.username and not event.message.by_bot):
                            if type(message) == str:
                                try:
                                    acc.send_message(event.message.chat_id, message)
                                    logger.info(f'Send {trigger} to {event.message.author} on {event.message.text}')
                                except Exception as e:
                                    logger.error(
                                        f'Error on send {trigger} to {event.message.author} on {event.message.text}',
                                        exc_info=True)
                            elif type(message) == list or type(message) == tuple:
                                for mes in message:
                                    try:
                                        if mes[0] != '/':
                                            acc.send_message(event.message.chat_id, mes)
                                        else:
                                            acc.send_image(event.message.chat_id, path_to_images + mes)
                                    except Exception as e:
                                        logger.error(
                                            f'Error on send {trigger} to {event.message.author} on {event.message.text}',
                                            exc_info=True)
                                logger.info(f'Send {trigger} to {event.message.author} on {event.message.text}')
                                break

        def get_messages_from_chat(message: FunPayAPI.types.Message) -> List[FunPayAPI.types.Message] | None:
            if message.chat_id not in runner.chats:
                attempts = 3
                while attempts:
                    attempts -= 1
                    try:
                        chat = runner.account.get_chats_histories({message.chat_id: message.author})
                        break
                    except Exception as e:
                        logger.error(f"Произошла ошибка {e} при обновлении чата {message.chat_id} {acc.username}",
                                     exc_info=True)
                        # logger.debug("TRACEBACK", exc_info=True)
                    sleep(1)
                else:
                    logger.error(f"Не удалось обновить чат {message.chat_id}: превышено кол-во попыток.")
                    return None
                runner.chats.update(chat)
            return runner.chats[message.chat_id]

        def main():
            for events in runner.listen(requests_delay=delay, disable_orders=True):
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
