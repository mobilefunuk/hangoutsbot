import hangups
import time
import plugins


def _initialise(bot):
    plugins.register_user_command(["tldr"])
    plugins.register_admin_command(["tldrecho"])
    bot.register_shared("plugin_tldr_shared", tldr_shared)


def tldrecho(bot, event, p_tldr_echo=None):
    """<br/>/bot <i><b>tldrecho</b> <group/PM></i><br/>Defines whether the full tldr is echoed to a PM or into the main chat.<br/><br/>e.g. /bot tldrecho PM"""

    # If no memory entry exists, create it.
    if not bot.memory.exists(['conversations']):
        bot.memory.set_by_path(['conversations'],{})
    if not bot.memory.exists(['conversations',event.conv_id]):
        bot.memory.set_by_path(['conversations',event.conv_id],{})

    bot.memory.set_by_path(['conversations', event.conv_id, 'tldr_echo'], p_tldr_echo)
    bot.memory.save()
    
    # If no tldr_echo setting specified, then the tldr_echo set for this hangout has been cleared.
    if p_tldr_echo is None:
        segments = [hangups.ChatMessageSegment('TLDR echo setting for this hangout has been cleared', is_bold=True)]
    else:
        # Get the current tldr_echo setting.
        segments = [hangups.ChatMessageSegment('TLDR echo for this hangout is:', is_bold=True),
                    hangups.ChatMessageSegment('\n', hangups.SegmentType.LINE_BREAK),
                    hangups.ChatMessageSegment(p_tldr_echo)]
    
    yield from bot.coro_send_message(event.conv_id, segments)


def tldr(bot, event, *args):
    """<br/>/bot <i><b>tldr</b> <message></i><br/>Adds a short message to a list saved for the conversation.<br/>All TLDRs can be retrieved using: /bot <i><b>tldr</b></i>, single tldr using: /bot <i><b>tldr</b> <number></i><br/>All TLDR entries can be deleted using: /bot <i><b>tldr clear</b></i>, single tldr entries using: /bot <i><b>tldr clear</b> <number></i><br/>Single TLDRs can be edited using /bot <i><b>tldr edit</b> <number> <new message></i><br/>"""

    ## Retrieve the current tldr echo status for the hangout.
    # If no memory entry exists, create it.
    if not bot.memory.exists(['conversations']):
        bot.memory.set_by_path(['conversations'],{})
    if not bot.memory.exists(['conversations',event.conv_id]):
        bot.memory.set_by_path(['conversations',event.conv_id],{})

    # Check per conversation setting in memory first, then global from config.json.
    # If nothing set, then set the bot default as False.

    if not bot.memory.exists(['conversations',event.conv_id,'tldr_echo']):
        if not bot.get_config_option('tldr_echo'):
            bot.config.set_by_path(["tldr_echo"], 'group')
            bot.config.save()
    
    if not bot.memory.exists(['conversations',event.conv_id,'tldr_echo']):
        mem_tldr_echo = bot.get_config_option('tldr_echo')
    else:
        mem_tldr_echo = bot.memory.get_by_path(['conversations', event.conv_id, 'tldr_echo'])

    message, display = tldr_base(bot, event.conv_id, list(args))
    print (display)
    print (mem_tldr_echo)
    if display is True and mem_tldr_echo == 'PM':
        yield from bot.coro_send_to_user_and_conversation(event.user.id_.chat_id, event.conv_id, message, ("<i>{}, I've sent you the info in a PM ;-)</i>").format(event.user.full_name))
    else:
        yield from bot.coro_send_message(event.conv_id, message)


def tldr_shared(bot, args):
    """
    Shares tldr functionality with other plugins
    :param bot: hangouts bot
    :param args: a dictionary which holds arguments.
    Must contain 'params' (tldr command parameters) and 'conv_id' (Hangouts conv_id)
    :return:
    """
    if not isinstance(args, dict):
        raise TypeError("args must be a dictionary")

    if 'params' not in args:
        raise KeyError("'params' key missing in args")

    if 'conv_id' not in args:
        raise KeyError("'conv_id' key missing in args")

    params = args['params']
    conv_id = args['conv_id']

    return_data, display = tldr_base(bot, conv_id, params)

    return return_data


def tldr_base(bot, conv_id, parameters):
    # parameters = list(args)

    # If no memory entry exists, create it.
    if not bot.memory.exists(['tldr']):
        bot.memory.set_by_path(['tldr'], {})
    if not bot.memory.exists(['tldr', conv_id]):
        bot.memory.set_by_path(['tldr', conv_id], {})

    conv_tldr = bot.memory.get_by_path(['tldr', conv_id])

    display = False
    if not parameters:
        display = True
    elif len(parameters) == 1 and parameters[0].isdigit():
        display = int(parameters[0]) - 1

    if display is not False:
        # Display all messages or a specific message
        html = []
        for num, timestamp in enumerate(sorted(conv_tldr, key=float)):
            if display is True or display == num:
                html.append(_("{}. {} <b>{} ago</b>").format(str(num + 1),
                                                             conv_tldr[timestamp],
                                                             _time_ago(float(timestamp))))

        if len(html) == 0:
            html.append(_("TL;DR not found"))
            display = False
        else:
            html.insert(0, _("<b>TL;DR ({} stored):</b>").format(len(conv_tldr)))
        message = _("\n".join(html))

        return message, display

    if parameters[0] == "clear":
        if len(parameters) == 2 and parameters[1].isdigit():
            sorted_keys = sorted(list(conv_tldr.keys()), key=float)
            key_index = int(parameters[1]) - 1
            if key_index < 0 or key_index >= len(sorted_keys):
                message = _("TL;DR #{} not found").format(parameters[1])
            else:
                popped_tldr = conv_tldr.pop(sorted_keys[key_index])
                bot.memory.set_by_path(['tldr', conv_id], conv_tldr)
                message = _('TL;DR #{} removed - "{}"').format(parameters[1], popped_tldr)
        else:
            bot.memory.set_by_path(['tldr', conv_id], {})
            message = _("All TL;DRs cleared")

        return message, display

    elif parameters[0] == "edit":
        if len(parameters) > 2 and parameters[1].isdigit():
            sorted_keys = sorted(list(conv_tldr.keys()), key=float)
            key_index = int(parameters[1]) - 1
            if key_index < 0 or key_index >= len(sorted_keys):
                message = _("TL;DR #{} not found").format(parameters[1])
            else:
                edited_tldr = conv_tldr[sorted_keys[key_index]]
                tldr = ' '.join(parameters[2:len(parameters)])
                conv_tldr[sorted_keys[key_index]] = tldr
                bot.memory.set_by_path(['tldr', conv_id], conv_tldr)
                message = _('TL;DR #{} edited - "{}" -> "{}"').format(parameters[1], edited_tldr, tldr)
        else:
            message = _('Unknown Command at "tldr edit"')

        return message, display

    elif parameters[0]:  ## need a better looking solution here
        tldr = ' '.join(parameters)
        if tldr:
            # Add message to list
            conv_tldr[str(time.time())] = tldr
            bot.memory.set_by_path(['tldr', conv_id], conv_tldr)
            message = _('<em>{}</em> added to TL;DR. Count: {}').format(tldr, len(conv_tldr))

            return message, display

    bot.memory.save()


def _time_ago(timestamp):
    time_difference = time.time() - timestamp
    if time_difference < 60:  # seconds
        return _("{}s").format(int(time_difference))
    elif time_difference < 60 * 60:  # minutes
        return _("{}m").format(int(time_difference / 60))
    elif time_difference < 60 * 60 * 24:  # hours
        return _("{}h").format(int(time_difference / (60 * 60)))
    else:
        return _("{}d").format(int(time_difference / (60 * 60 * 24)))
