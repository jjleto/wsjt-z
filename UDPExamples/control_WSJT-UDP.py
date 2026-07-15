#!/usr/bin/env python3
# WSJT-Z Control via UDP
# Schema 3+ support for remote control of WSJT-Z features
# DE K7MHI

import socket
import struct
import sys
import argparse
import time
from enum import IntEnum
from datetime import datetime


class MessageType(IntEnum):
    """WSJT-Z UDP Message Types"""
    Heartbeat = 0
    Status = 1
    Decode = 2
    Clear = 3
    Reply = 4
    QSOLogged = 5
    Close = 6
    Replay = 7
    HaltTx = 8
    FreeText = 9
    WSPRDecode = 10
    Location = 11
    LoggedADIF = 12
    HighlightCallsign = 13
    SwitchConfiguration = 14
    Configure = 15
    AnnotationInfo = 16


class QtDataStreamWriter:
    """Writes Qt-compatible binary data streams (big-endian)"""
    
    def __init__(self):
        self.data = bytearray()
    
    def write_uint32(self, value):
        self.data.extend(struct.pack('>I', value))
    
    def write_int32(self, value):
        self.data.extend(struct.pack('>i', value))
    
    def write_uint16(self, value):
        self.data.extend(struct.pack('>H', value))
    
    def write_uint8(self, value):
        self.data.extend(struct.pack('>B', value))
    
    def write_bool(self, value):
        self.data.extend(struct.pack('>B', 1 if value else 0))
    
    def write_double(self, value):
        self.data.extend(struct.pack('>d', value))
    
    def write_float(self, value):
        self.data.extend(struct.pack('>f', value))
    
    def write_qtime(self, qtime_obj):
        """Write QTime as milliseconds since midnight"""
        if isinstance(qtime_obj, str):
            # Parse "HH:MM:SS" or "HH:MM:SS.mmm"
            parts = qtime_obj.split(':')
            if len(parts) >= 2:
                h = int(parts[0])
                m = int(parts[1])
                s = int(parts[2].split('.')[0]) if len(parts) > 2 else 0
                ms = int(parts[2].split('.')[1]) if '.' in parts[2] else 0
                ms_total = (h * 3600 + m * 60 + s) * 1000 + ms
                self.write_uint32(ms_total)
            else:
                self.write_uint32(0)
        else:
            self.write_uint32(qtime_obj)
    
    def write_qcolor(self, color_str):
        """Write QColor as 0xAARRGGBB"""
        if color_str.startswith('0x') or color_str.startswith('0X'):
            color_val = int(color_str, 16)
        else:
            # Try to parse as decimal
            color_val = int(color_str)
        self.write_uint32(color_val)
    
    def write_utf8(self, text):
        """Write a UTF-8 string as QByteArray (size-prefixed)"""
        if text is None or text == '':
            self.write_uint32(0xffffffff)  # null string
        else:
            encoded = text.encode('utf-8')
            self.write_uint32(len(encoded))
            self.data.extend(encoded)
    
    def get_bytes(self):
        return bytes(self.data)


def send_udp_message(server_address, server_port, message):
    """Send UDP message to WSJT-X"""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(message, (server_address, server_port))
        sock.close()
        return True
    except Exception as e:
        print(f"Error sending message: {e}", file=sys.stderr)
        return False


# ============================================================================
# Message Builders
# ============================================================================

def build_clear_decodes(message_id, window=0):
    """Build Clear Decodes message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.Clear)
    writer.write_utf8(message_id)
    writer.write_uint8(window)
    return writer.get_bytes()


def build_reply(message_id, time_str, snr, delta_time, delta_frequency, mode, message_text, 
                low_confidence=False, modifiers=0):
    """Build Reply message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.Reply)
    writer.write_utf8(message_id)
    writer.write_qtime(time_str)
    writer.write_int32(snr)
    writer.write_float(delta_time)
    writer.write_uint32(delta_frequency)
    writer.write_utf8(mode)
    writer.write_utf8(message_text)
    writer.write_bool(low_confidence)
    writer.write_uint8(modifiers)
    return writer.get_bytes()


def build_replay(message_id):
    """Build Replay message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.Replay)
    writer.write_utf8(message_id)
    return writer.get_bytes()


def build_halt_tx(message_id, auto_only=False):
    """Build HaltTx message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.HaltTx)
    writer.write_utf8(message_id)
    writer.write_bool(auto_only)
    return writer.get_bytes()


def build_free_text(message_id, text, send=False):
    """Build FreeText message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.FreeText)
    writer.write_utf8(message_id)
    writer.write_utf8(text)
    writer.write_bool(send)
    return writer.get_bytes()


def build_location(message_id, location):
    """Build Location message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.Location)
    writer.write_utf8(message_id)
    writer.write_utf8(location)
    return writer.get_bytes()


def build_highlight_callsign(message_id, callsign, bg_color='0xffffffff', fg_color='0xff000000', last_only=False):
    """Build HighlightCallsign message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.HighlightCallsign)
    writer.write_utf8(message_id)
    writer.write_utf8(callsign)
    writer.write_qcolor(bg_color)
    writer.write_qcolor(fg_color)
    writer.write_bool(last_only)
    return writer.get_bytes()


def build_switch_configuration(message_id, config_name):
    """Build SwitchConfiguration message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.SwitchConfiguration)
    writer.write_utf8(message_id)
    writer.write_utf8(config_name)
    return writer.get_bytes()


def build_configure(message_id, mode='', frequency_tolerance=0xffffffff, 
                   submode='', fast_mode=False, tr_period=0xffffffff,
                   rx_df=0xffffffff, dx_call='', dx_grid='', 
                   generate_messages=False, auto_cq_enabled=False, auto_call_enabled=False,
                   schema=None):
    """Build Configure message"""
    writer = QtDataStreamWriter()
    
    # Auto-detect schema: use 3 only if AutoCQ/AutoCall fields are being set
    if schema is None:
        schema = 3 if (auto_cq_enabled or auto_call_enabled) else 2
    
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(schema)
    writer.write_uint32(MessageType.Configure)
    writer.write_utf8(message_id)
    
    # Schema 2 fields
    writer.write_utf8(mode)
    writer.write_uint32(frequency_tolerance)
    writer.write_utf8(submode)
    writer.write_bool(fast_mode)
    writer.write_uint32(tr_period)
    writer.write_uint32(rx_df)
    writer.write_utf8(dx_call)
    writer.write_utf8(dx_grid)
    writer.write_bool(generate_messages)
    
    # Schema 3+ fields
    if schema >= 3:
        writer.write_bool(auto_cq_enabled)
        writer.write_bool(auto_call_enabled)
    
    return writer.get_bytes()


def build_close(message_id):
    """Build Close message"""
    writer = QtDataStreamWriter()
    writer.write_uint32(0xadbccbda)  # magic
    writer.write_uint32(2)  # schema
    writer.write_uint32(MessageType.Close)
    writer.write_utf8(message_id)
    return writer.get_bytes()


# ============================================================================
# Subcommand Handlers
# ============================================================================

def cmd_configure(args):
    """Handle 'configure' subcommand"""
    kwargs = {
        'mode': args.mode or '',
        'frequency_tolerance': args.freq_tol if args.freq_tol else 0xffffffff,
        'submode': args.submode or '',
        'fast_mode': args.fast_mode,
        'tr_period': args.tr_period if args.tr_period else 0xffffffff,
        'rx_df': args.rx_df if args.rx_df else 0xffffffff,
        'dx_call': args.dx_call or '',
        'dx_grid': args.dx_grid or '',
        'generate_messages': args.generate_messages,
        'schema': args.schema,
    }
    
    if args.auto_cq is not None:
        kwargs['auto_cq_enabled'] = args.auto_cq
    if args.auto_call is not None:
        kwargs['auto_call_enabled'] = args.auto_call
    
    message = build_configure(args.id, **kwargs)
    
    if args.verbose:
        print("=" * 60)
        print("Configure Message")
        print("=" * 60)
        print(f"Target: {args.host}:{args.port}")
        print(f"Client ID: {args.id}")
        actual_schema = args.schema if args.schema else (3 if (args.auto_cq or args.auto_call) else 2)
        print(f"Schema: {actual_schema}")
        print()
        if args.mode:
            print(f"Mode:     {args.mode}")
        if args.submode:
            print(f"Submode:  {args.submode}")
        if args.fast_mode:
            print(f"Fast Mode: enabled")
        if args.freq_tol:
            print(f"Freq Tol: {args.freq_tol} Hz")
        if args.tr_period:
            print(f"T/R Period: {args.tr_period}s")
        if args.rx_df:
            print(f"RX DF: {args.rx_df} Hz")
        if args.dx_call:
            print(f"DX Call: {args.dx_call}")
        if args.dx_grid:
            print(f"DX Grid: {args.dx_grid}")
        if args.auto_cq is not None:
            print(f"AutoCQ:   {'ENABLE' if args.auto_cq else 'DISABLE'}")
        if args.auto_call is not None:
            print(f"AutoCall: {'ENABLE' if args.auto_call else 'DISABLE'}")
        print()
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent successfully")
        else:
            print("OK")
        return 0
    else:
        print("✗ Failed to send message", file=sys.stderr)
        return 1


def cmd_switch_config(args):
    """Handle 'switch-config' subcommand"""
    if not args.name:
        print("Error: configuration name required", file=sys.stderr)
        return 1
    
    message = build_switch_configuration(args.id, args.name)
    
    if args.verbose:
        print(f"Switching to configuration: {args.name}")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_location(args):
    """Handle 'location' subcommand"""
    if not args.location:
        print("Error: location required", file=sys.stderr)
        return 1
    
    message = build_location(args.id, args.location)
    
    if args.verbose:
        print(f"Setting location: {args.location}")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_highlight(args):
    """Handle 'highlight' subcommand"""
    if not args.callsign:
        print("Error: callsign required", file=sys.stderr)
        return 1
    
    message = build_highlight_callsign(args.id, args.callsign, args.bg_color, args.fg_color, args.last_only)
    
    if args.verbose:
        print(f"Highlighting: {args.callsign}")
        if args.bg_color != '0xffffffff':
            print(f"  Background: {args.bg_color}")
        if args.fg_color != '0xff000000':
            print(f"  Foreground: {args.fg_color}")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_reply(args):
    """Handle 'reply' subcommand"""
    if not args.time or not args.mode or not args.message:
        print("Error: time, mode, and message required", file=sys.stderr)
        return 1
    
    message = build_reply(args.id, args.time, args.snr, args.delta_time, args.delta_frequency,
                          args.mode, args.message, args.low_confidence, args.modifiers)
    
    if args.verbose:
        print(f"Sending reply at {args.time}")
        print(f"  SNR: {args.snr}")
        print(f"  Mode: {args.mode}")
        print(f"  Message: {args.message}")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_free_text(args):
    """Handle 'free-text' subcommand"""
    if not args.text:
        print("Error: text required", file=sys.stderr)
        return 1
    
    message = build_free_text(args.id, args.text, args.send)
    
    if args.verbose:
        print(f"Setting free text: {args.text}")
        if args.send:
            print("  (will send immediately)")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_halt_tx(args):
    """Handle 'halt-tx' subcommand"""
    message = build_halt_tx(args.id, args.auto_only)
    
    if args.verbose:
        if args.auto_only:
            print("Halting auto TX")
        else:
            print("Halting TX immediately")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_clear_decodes(args):
    """Handle 'clear-decodes' subcommand"""
    message = build_clear_decodes(args.id, args.window)
    
    if args.verbose:
        print(f"Clearing decode window: {args.window}")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_replay(args):
    """Handle 'replay' subcommand"""
    message = build_replay(args.id)
    
    if args.verbose:
        print("Replaying all decodes")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


def cmd_close(args):
    """Handle 'close' subcommand"""
    message = build_close(args.id)
    
    if args.verbose:
        print("Closing connection")
    
    if send_udp_message(args.host, args.port, message):
        if args.verbose:
            print("✓ Message sent")
        else:
            print("OK")
        return 0
    else:
        return 1


# ============================================================================
# Main
# ============================================================================

if __name__ == "__main__":
    DEFAULT_SERVER = 'localhost'
    DEFAULT_PORT = 2237
    DEFAULT_ID = 'ControlClient'
    
    parser = argparse.ArgumentParser(
        description='Control WSJT-X via UDP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  # Configure WSJT-X
  %(prog)s configure --auto-cq --mode FT8
  
  # Switch configuration
  %(prog)s switch-config --name "2m_beacon"
  
  # Set location
  %(prog)s location --location "EN91WI"
  
  # Highlight a callsign
  %(prog)s highlight --callsign "K7ABC" --bg-color "0xff0000"
  
  # Send auto reply
  %(prog)s reply --time "12:34:56" --snr -5 --mode "FT8" --message "RST 579"
  
  # Set free text
  %(prog)s free-text --text "CQ"
  
  # Halt transmission
  %(prog)s halt-tx
  
  # Clear decodes
  %(prog)s clear-decodes --window 0
  
  # Replay all decodes
  %(prog)s replay
  
  # Close connection
  %(prog)s close
        ''')
    
    parser.add_argument('--host', default=DEFAULT_SERVER,
                       help=f'WSJT-X server address (default: {DEFAULT_SERVER})')
    parser.add_argument('--port', type=int, default=DEFAULT_PORT,
                       help=f'WSJT-X UDP port (default: {DEFAULT_PORT})')
    parser.add_argument('--id', default=DEFAULT_ID,
                       help=f'Client identifier (default: {DEFAULT_ID})')
    parser.add_argument('-v', '--verbose', action='store_true',
                       help='Show message details')
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # ========== Configure ==========
    config_parser = subparsers.add_parser('configure', help='Configure WSJT-X settings')
    config_parser.add_argument('--mode', help='Mode (FT8, FT4, JT65, etc.)')
    config_parser.add_argument('--submode', help='Submode character')
    config_parser.add_argument('--fast-mode', action='store_true', help='Enable fast mode')
    config_parser.add_argument('--freq-tol', type=int, help='Frequency tolerance in Hz')
    config_parser.add_argument('--tr-period', type=int, help='T/R period in seconds')
    config_parser.add_argument('--rx-df', type=int, help='RX audio frequency offset in Hz')
    config_parser.add_argument('--dx-call', help='DX call to work')
    config_parser.add_argument('--dx-grid', help='DX grid locator')
    config_parser.add_argument('--generate-messages', action='store_true',
                              help='Enable automatic message generation')
    config_parser.add_argument('--auto-cq', action='store_true', dest='auto_cq',
                              help='Enable AutoCQ mode')
    config_parser.add_argument('--no-auto-cq', action='store_false', dest='auto_cq',
                              help='Disable AutoCQ mode')
    config_parser.add_argument('--auto-call', action='store_true', dest='auto_call',
                              help='Enable AutoCall mode')
    config_parser.add_argument('--no-auto-call', action='store_false', dest='auto_call',
                              help='Disable AutoCall mode')
    config_parser.add_argument('--schema', type=int, choices=[2, 3],
                              help='Schema version (default: auto-detect)')
    config_parser.set_defaults(func=cmd_configure, auto_cq=None, auto_call=None)
    
    # ========== Switch Configuration ==========
    switch_parser = subparsers.add_parser('switch-config', help='Switch WSJT-X configuration')
    switch_parser.add_argument('--name', required=True, help='Configuration name to switch to')
    switch_parser.set_defaults(func=cmd_switch_config)
    
    # ========== Location ==========
    loc_parser = subparsers.add_parser('location', help='Set location')
    loc_parser.add_argument('--location', required=True, help='Grid locator (e.g., EN91WI)')
    loc_parser.set_defaults(func=cmd_location)
    
    # ========== Highlight Callsign ==========
    hl_parser = subparsers.add_parser('highlight', help='Highlight a callsign')
    hl_parser.add_argument('--callsign', required=True, help='Callsign to highlight')
    hl_parser.add_argument('--bg-color', default='0xffffffff',
                          help='Background color as 0xAARRGGBB (default: white)')
    hl_parser.add_argument('--fg-color', default='0xff000000',
                          help='Foreground color as 0xAARRGGBB (default: black)')
    hl_parser.add_argument('--last-only', action='store_true',
                          help='Highlight only the last occurrence')
    hl_parser.set_defaults(func=cmd_highlight)
    
    # ========== Reply ==========
    reply_parser = subparsers.add_parser('reply', help='Send automated reply')
    reply_parser.add_argument('--time', required=True, help='Time of decode (HH:MM:SS)')
    reply_parser.add_argument('--snr', type=int, default=0, help='Signal-to-noise ratio')
    reply_parser.add_argument('--delta-time', type=float, default=0.0,
                             help='Time offset in seconds')
    reply_parser.add_argument('--delta-frequency', type=int, default=0,
                             help='Frequency offset in Hz')
    reply_parser.add_argument('--mode', required=True, help='Mode (FT8, etc.)')
    reply_parser.add_argument('--message', required=True, help='Message to send')
    reply_parser.add_argument('--low-confidence', action='store_true',
                             help='Mark as low confidence decode')
    reply_parser.add_argument('--modifiers', type=int, default=0, help='Message modifiers')
    reply_parser.set_defaults(func=cmd_reply)
    
    # ========== Free Text ==========
    ftext_parser = subparsers.add_parser('free-text', help='Set free text message')
    ftext_parser.add_argument('--text', required=True, help='Text message')
    ftext_parser.add_argument('--send', action='store_true',
                             help='Send immediately')
    ftext_parser.set_defaults(func=cmd_free_text)
    
    # ========== Halt TX ==========
    halt_parser = subparsers.add_parser('halt-tx', help='Halt transmission')
    halt_parser.add_argument('--auto-only', action='store_true',
                            help='Halt auto TX only, keep manual enabled')
    halt_parser.set_defaults(func=cmd_halt_tx)
    
    # ========== Clear Decodes ==========
    clear_parser = subparsers.add_parser('clear-decodes', help='Clear decode windows')
    clear_parser.add_argument('--window', type=int, default=0,
                             help='Window to clear (0=both, 1=wide, 2=narrow)')
    clear_parser.set_defaults(func=cmd_clear_decodes)
    
    # ========== Replay ==========
    replay_parser = subparsers.add_parser('replay', help='Replay all decodes')
    replay_parser.set_defaults(func=cmd_replay)
    
    # ========== Close ==========
    close_parser = subparsers.add_parser('close', help='Close connection')
    close_parser.set_defaults(func=cmd_close)
    
    args = parser.parse_args()
    
    if not hasattr(args, 'func'):
        parser.print_help()
        sys.exit(1)
    
    sys.exit(args.func(args))
