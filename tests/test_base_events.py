"""Tests for base_events.py"""

import errno
import logging
import socket
import time
import unittest
import unittest.mock
from testsupport import find_unused_port, IPV6_ENABLED

import asyncio
from asyncio import base_events
from asyncio import constants
from asyncio import test_utils

import gpotato
from gi.repository import GLib
from gi.repository import GObject

gpotato.BaseGLibEventLoop.init_class()
GObject.threads_init()

class BaseEventLoopTests(unittest.TestCase):

    def setUp(self):
        self.loop = gpotato.GLibEventLoop(GLib.main_context_default())
        self.loop.set_debug(True)
        self.loop._selector = unittest.mock.Mock()
        asyncio.set_event_loop(None)

    @unittest.skip
    def test_not_implemented(self):
        m = unittest.mock.Mock()
        self.assertRaises(
            NotImplementedError,
            self.loop._make_socket_transport, m, m)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_ssl_transport, m, m, m, m)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_datagram_transport, m, m)
        self.assertRaises(
            NotImplementedError, self.loop._process_events, [])
        self.assertRaises(
            NotImplementedError, self.loop._write_to_self)
        self.assertRaises(
            NotImplementedError, self.loop._read_from_self)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_read_pipe_transport, m, m)
        self.assertRaises(
            NotImplementedError,
            self.loop._make_write_pipe_transport, m, m)
        gen = self.loop._make_subprocess_transport(m, m, m, m, m, m, m)
        self.assertRaises(NotImplementedError, next, iter(gen))

    @unittest.skip
    def test__add_callback_handle(self):
        h = asyncio.Handle(lambda: False, (), self.loop)

        self.loop._add_callback(h)
        self.assertFalse(self.loop._scheduled)
        self.assertIn(h, self.loop._ready)

    @unittest.skip
    def test__add_callback_timer(self):
        h = asyncio.TimerHandle(time.monotonic()+10, lambda: False, (), self.loop)

        self.loop._add_callback(h)
        self.assertIn(h, self.loop._scheduled)

    @unittest.skip
    def test__add_callback_cancelled_handle(self):
        h = asyncio.Handle(lambda: False, (), self.loop)
        h.cancel()

        self.loop._add_callback(h)
        self.assertFalse(self.loop._scheduled)
        self.assertFalse(self.loop._ready)

    def test_set_default_executor(self):
        executor = unittest.mock.Mock()
        self.loop.set_default_executor(executor)
        self.assertIs(executor, self.loop._default_executor)

    def test_getnameinfo(self):
        sockaddr = unittest.mock.Mock()
        self.loop.run_in_executor = unittest.mock.Mock()
        self.loop.getnameinfo(sockaddr)
        self.assertEqual(
            (None, socket.getnameinfo, sockaddr, 0),
            self.loop.run_in_executor.call_args[0])

    def test_call_soon(self):
        def cb():
            pass

        h = self.loop.call_soon(cb)
        self.assertEqual(h._callback, cb)
        self.assertIsInstance(h, asyncio.Handle)
        self.assertIn(h, self.loop._ready)

    def test_call_later(self):
        def cb():
            pass

        h = self.loop.call_later(10.0, cb)
        self.assertIsInstance(h, gpotato.GLibHandle)
#        self.assertIn(h, self.loop._scheduled)
        self.assertNotIn(h, self.loop._ready)

    @unittest.expectedFailure
    def test_call_later_negative_delays(self):
        calls = []

        def cb(arg):
            calls.append(arg)

        self.loop._process_events = unittest.mock.Mock()
        self.loop.call_later(-1, cb, 'a')
        self.loop.call_later(-2, cb, 'b')
        test_utils.run_briefly(self.loop)
        self.assertEqual(calls, ['b', 'a'])  # FIXME: Currently doesn't order

    def test_time_and_call_at(self):
        def cb():
            self.loop.stop()

        self.loop._process_events = unittest.mock.Mock()
        delay = 0.1

        when = self.loop.time() + delay
        self.loop.call_at(when, cb)
        t0 = self.loop.time()
        self.loop.run_forever()
        dt = self.loop.time() - t0

        # 50 ms: maximum granularity of the event loop
        self.assertGreaterEqual(dt, delay - 0.050, dt)
        # tolerate a difference of +800 ms because some Python buildbots
        # are really slow
        self.assertLessEqual(dt, 0.9, dt)

    def test_run_once_in_executor_handle(self):
        def cb():
            pass

        self.assertRaises(
            AssertionError, self.loop.run_in_executor,
            None, asyncio.Handle(cb, (), self.loop), ('',))
        self.assertRaises(
            AssertionError, self.loop.run_in_executor,
            None, asyncio.TimerHandle(10, cb, (), self.loop))

    def test_run_once_in_executor_cancelled(self):
        def cb():
            pass
        h = asyncio.Handle(cb, (), self.loop)
        h.cancel()

        f = self.loop.run_in_executor(None, h)
        self.assertIsInstance(f, asyncio.Future)
        self.assertTrue(f.done())
        self.assertIsNone(f.result())

    def test_run_once_in_executor_plain(self):
        def cb():
            pass
        h = asyncio.Handle(cb, (), self.loop)
        f = asyncio.Future(loop=self.loop)
        executor = unittest.mock.Mock()
        executor.submit.return_value = f

        self.loop.set_default_executor(executor)

        res = self.loop.run_in_executor(None, h)
        self.assertIs(f, res)

        executor = unittest.mock.Mock()
        executor.submit.return_value = f
        res = self.loop.run_in_executor(executor, h)
        self.assertIs(f, res)
        self.assertTrue(executor.submit.called)

        f.cancel()  # Don't complain about abandoned Future.

    @unittest.skip
    def test__run_once(self):
        h1 = asyncio.TimerHandle(time.monotonic() + 5.0, lambda: True, (), self.loop)
        h2 = asyncio.TimerHandle(time.monotonic() + 10.0, lambda: True, (), self.loop)

        h1.cancel()

        self.loop._process_events = unittest.mock.Mock()
        self.loop._scheduled.append(h1)
        self.loop._scheduled.append(h2)
        self.loop._run_once()

        t = self.loop._selector.select.call_args[0][0]
        self.assertTrue(9.5 < t < 10.5, t)
        self.assertEqual([h2], self.loop._scheduled)
        self.assertTrue(self.loop._process_events.called)

    @unittest.skip
    @unittest.mock.patch('asyncio.base_events.time')
    @unittest.mock.patch('asyncio.base_events.logger')
    def test__run_once_logging(self, m_logger, m_time):
        # Log to INFO level if timeout > 1.0 sec.
        idx = -1
        data = [10.0, 10.0, 12.0, 13.0]

        def monotonic():
            nonlocal data, idx
            idx += 1
            return data[idx]

        m_time.monotonic = monotonic

        self.loop._scheduled.append(
            asyncio.TimerHandle(11.0, lambda: True, (), self.loop))
        self.loop._process_events = unittest.mock.Mock()
        self.loop._run_once()
        self.assertEqual(logging.INFO, m_logger.log.call_args[0][0])

        idx = -1
        data = [10.0, 10.0, 10.3, 13.0]
        self.loop._scheduled = [asyncio.TimerHandle(11.0, lambda:True, (), self.loop)]
        self.loop._run_once()
        self.assertEqual(logging.DEBUG, m_logger.log.call_args[0][0])

    @unittest.skip
    def test__run_once_schedule_handle(self):
        handle = None
        processed = False

        def cb(loop):
            nonlocal processed, handle
            processed = True
            handle = loop.call_soon(lambda: True)

        h = asyncio.TimerHandle(time.monotonic() - 1, cb, (self.loop,), self.loop)

        self.loop._process_events = unittest.mock.Mock()
        self.loop._scheduled.append(h)
        self.loop._run_once()

        self.assertTrue(processed)
        self.assertEqual([handle], list(self.loop._ready), self.loop)

    def test_run_until_complete_type_error(self):
        self.assertRaises(
            TypeError, self.loop.run_until_complete, 'blah')


class MyProto(asyncio.Protocol):
    done = None

    def __init__(self, create_future=False):
        self.state = 'INITIAL'
        self.nbytes = 0
        if create_future:
            self.done = asyncio.Future()

    def connection_made(self, transport):
        self.transport = transport
        assert self.state == 'INITIAL', self.state
        self.state = 'CONNECTED'
        transport.write(b'GET / HTTP/1.0\r\nHost: example.com\r\n\r\n')

    def data_received(self, data):
        assert self.state == 'CONNECTED', self.state
        self.nbytes += len(data)

    def eof_received(self):
        assert self.state == 'CONNECTED', self.state
        self.state = 'EOF'

    def connection_lost(self, exc):
        assert self.state in ('CONNECTED', 'EOF'), self.state
        self.state = 'CLOSED'
        if self.done:
            self.done.set_result(None)


class MyDatagramProto(asyncio.DatagramProtocol):
    done = None

    def __init__(self, create_future=False):
        self.state = 'INITIAL'
        self.nbytes = 0
        if create_future:
            self.done = asyncio.Future()

    def connection_made(self, transport):
        self.transport = transport
        assert self.state == 'INITIAL', self.state
        self.state = 'INITIALIZED'

    def datagram_received(self, data, addr):
        assert self.state == 'INITIALIZED', self.state
        self.nbytes += len(data)

    def error_received(self, exc):
        assert self.state == 'INITIALIZED', self.state

    def connection_lost(self, exc):
        assert self.state == 'INITIALIZED', self.state
        self.state = 'CLOSED'
        if self.done:
            self.done.set_result(None)


class BaseEventLoopWithSelectorTests(unittest.TestCase):

    def setUp(self):
        self.loop = asyncio.new_event_loop()
        self.loop.set_debug(True)
        asyncio.set_event_loop(None)

    def tearDown(self):
        self.loop.close()

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_connection_multiple_errors(self, m_socket):

        class MyProto(asyncio.Protocol):
            pass

        @asyncio.coroutine
        def getaddrinfo(*args, **kw):
            yield from []
            return [(2, 1, 6, '', ('107.6.106.82', 80)),
                    (2, 1, 6, '', ('107.6.106.82', 80))]

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)

        idx = -1
        errors = ['err1', 'err2']

        def _socket(*args, **kw):
            nonlocal idx, errors
            idx += 1
            raise OSError(errors[idx])

        m_socket.socket = _socket

        self.loop.getaddrinfo = getaddrinfo_task

        coro = self.loop.create_connection(MyProto, 'example.com', 80)
        with self.assertRaises(OSError) as cm:
            self.loop.run_until_complete(coro)

        self.assertEqual(str(cm.exception), 'Multiple exceptions: err1, err2')

    def test_create_connection_host_port_sock(self):
        coro = self.loop.create_connection(
            MyProto, 'example.com', 80, sock=object())
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)

    def test_create_connection_no_host_port_sock(self):
        coro = self.loop.create_connection(MyProto)
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)

    def test_create_connection_no_getaddrinfo(self):
        @asyncio.coroutine
        def getaddrinfo(*args, **kw):
            yield from []

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)

        self.loop.getaddrinfo = getaddrinfo_task
        coro = self.loop.create_connection(MyProto, 'example.com', 80)
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

    def test_create_connection_connect_err(self):
        @asyncio.coroutine
        def getaddrinfo(*args, **kw):
            yield from []
            return [(2, 1, 6, '', ('107.6.106.82', 80))]

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)

        self.loop.getaddrinfo = getaddrinfo_task
        self.loop.sock_connect = unittest.mock.Mock()
        self.loop.sock_connect.side_effect = OSError

        coro = self.loop.create_connection(MyProto, 'example.com', 80)
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

    def test_create_connection_multiple(self):
        @asyncio.coroutine
        def getaddrinfo(*args, **kw):
            return [(2, 1, 6, '', ('0.0.0.1', 80)),
                    (2, 1, 6, '', ('0.0.0.2', 80))]

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)

        self.loop.getaddrinfo = getaddrinfo_task
        self.loop.sock_connect = unittest.mock.Mock()
        self.loop.sock_connect.side_effect = OSError

        coro = self.loop.create_connection(
            MyProto, 'example.com', 80, family=socket.AF_INET)
        with self.assertRaises(OSError):
            self.loop.run_until_complete(coro)

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_connection_multiple_errors_local_addr(self, m_socket):

        def bind(addr):
            if addr[0] == '0.0.0.1':
                err = OSError('Err')
                err.strerror = 'Err'
                raise err

        m_socket.socket.return_value.bind = bind

        @asyncio.coroutine
        def getaddrinfo(*args, **kw):
            return [(2, 1, 6, '', ('0.0.0.1', 80)),
                    (2, 1, 6, '', ('0.0.0.2', 80))]

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)

        self.loop.getaddrinfo = getaddrinfo_task
        self.loop.sock_connect = unittest.mock.Mock()
        self.loop.sock_connect.side_effect = OSError('Err2')

        coro = self.loop.create_connection(
            MyProto, 'example.com', 80, family=socket.AF_INET,
            local_addr=(None, 8080))
        with self.assertRaises(OSError) as cm:
            self.loop.run_until_complete(coro)

        self.assertTrue(str(cm.exception).startswith('Multiple exceptions: '))
        self.assertTrue(m_socket.socket.return_value.close.called)

    def test_create_connection_no_local_addr(self):
        @asyncio.coroutine
        def getaddrinfo(host, *args, **kw):
            if host == 'example.com':
                return [(2, 1, 6, '', ('107.6.106.82', 80)),
                        (2, 1, 6, '', ('107.6.106.82', 80))]
            else:
                return []

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)
        self.loop.getaddrinfo = getaddrinfo_task

        coro = self.loop.create_connection(
            MyProto, 'example.com', 80, family=socket.AF_INET,
            local_addr=(None, 8080))
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

    def test_create_connection_ssl_server_hostname_default(self):
        self.loop.getaddrinfo = unittest.mock.Mock()

        def mock_getaddrinfo(*args, **kwds):
            f = asyncio.Future(loop=self.loop)
            f.set_result([(socket.AF_INET, socket.SOCK_STREAM,
                           socket.SOL_TCP, '', ('1.2.3.4', 80))])
            return f

        self.loop.getaddrinfo.side_effect = mock_getaddrinfo
        self.loop.sock_connect = unittest.mock.Mock()
        self.loop.sock_connect.return_value = ()
        self.loop._make_ssl_transport = unittest.mock.Mock()

        class _SelectorTransportMock:
            _sock = None

            def close(self):
                self._sock.close()

            def get_extra_info(self, name, default=None):
                return "dummy:get_extra_info"

        def mock_make_ssl_transport(sock, protocol, sslcontext, waiter,
                                    **kwds):
            waiter.set_result(None)
            transport = _SelectorTransportMock()
            transport._sock = sock
            return transport

        self.loop._make_ssl_transport.side_effect = mock_make_ssl_transport
        ANY = unittest.mock.ANY
        # First try the default server_hostname.
        self.loop._make_ssl_transport.reset_mock()
        coro = self.loop.create_connection(MyProto, 'python.org', 80, ssl=True)
        transport, _ = self.loop.run_until_complete(coro)
        transport.close()
        self.loop._make_ssl_transport.assert_called_with(
            ANY, ANY, ANY, ANY,
            server_side=False,
            server_hostname='python.org')
        # Next try an explicit server_hostname.
        self.loop._make_ssl_transport.reset_mock()
        coro = self.loop.create_connection(MyProto, 'python.org', 80, ssl=True,
                                           server_hostname='perl.com')
        transport, _ = self.loop.run_until_complete(coro)
        transport.close()
        self.loop._make_ssl_transport.assert_called_with(
            ANY, ANY, ANY, ANY,
            server_side=False,
            server_hostname='perl.com')
        # Finally try an explicit empty server_hostname.
        self.loop._make_ssl_transport.reset_mock()
        coro = self.loop.create_connection(MyProto, 'python.org', 80, ssl=True,
                                           server_hostname='')
        transport, _ = self.loop.run_until_complete(coro)
        transport.close()
        self.loop._make_ssl_transport.assert_called_with(ANY, ANY, ANY, ANY,
                                                         server_side=False,
                                                         server_hostname='')

    def test_create_connection_no_ssl_server_hostname_errors(self):
        # When not using ssl, server_hostname must be None.
        coro = self.loop.create_connection(MyProto, 'python.org', 80,
                                           server_hostname='')
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)
        coro = self.loop.create_connection(MyProto, 'python.org', 80,
                                           server_hostname='python.org')
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)

    def test_create_connection_ssl_server_hostname_errors(self):
        # When using ssl, server_hostname may be None if host is non-empty.
        coro = self.loop.create_connection(MyProto, '', 80, ssl=True)
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)
        coro = self.loop.create_connection(MyProto, None, 80, ssl=True)
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)
        sock = socket.socket()
        coro = self.loop.create_connection(MyProto, None, None,
                                           ssl=True, sock=sock)
        self.addCleanup(sock.close)
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)

    def test_create_server_empty_host(self):
        # if host is empty string use None instead
        host = object()

        @asyncio.coroutine
        def getaddrinfo(*args, **kw):
            nonlocal host
            host = args[0]
            yield from []

        def getaddrinfo_task(*args, **kwds):
            return asyncio.Task(getaddrinfo(*args, **kwds), loop=self.loop)

        self.loop.getaddrinfo = getaddrinfo_task
        fut = self.loop.create_server(MyProto, '', 0)
        self.assertRaises(OSError, self.loop.run_until_complete, fut)
        self.assertIsNone(host)

    def test_create_server_host_port_sock(self):
        fut = self.loop.create_server(
            MyProto, '0.0.0.0', 0, sock=object())
        self.assertRaises(ValueError, self.loop.run_until_complete, fut)

    def test_create_server_no_host_port_sock(self):
        fut = self.loop.create_server(MyProto)
        self.assertRaises(ValueError, self.loop.run_until_complete, fut)

    def test_create_server_no_getaddrinfo(self):
        getaddrinfo = self.loop.getaddrinfo = unittest.mock.Mock()
        getaddrinfo.return_value = []

        f = self.loop.create_server(MyProto, '0.0.0.0', 0)
        self.assertRaises(OSError, self.loop.run_until_complete, f)

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_server_cant_bind(self, m_socket):

        class Err(OSError):
            strerror = 'error'

        m_socket.getaddrinfo.return_value = [
            (2, 1, 6, '', ('127.0.0.1', 10100))]
        m_sock = m_socket.socket.return_value = unittest.mock.Mock()
        m_sock.bind.side_effect = Err

        fut = self.loop.create_server(MyProto, '0.0.0.0', 0)
        self.assertRaises(OSError, self.loop.run_until_complete, fut)
        self.assertTrue(m_sock.close.called)

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_datagram_endpoint_no_addrinfo(self, m_socket):
        m_socket.getaddrinfo.return_value = []

        coro = self.loop.create_datagram_endpoint(
            MyDatagramProto, local_addr=('localhost', 0))
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

    def test_create_datagram_endpoint_addr_error(self):
        coro = self.loop.create_datagram_endpoint(
            MyDatagramProto, local_addr='localhost')
        self.assertRaises(
            AssertionError, self.loop.run_until_complete, coro)
        coro = self.loop.create_datagram_endpoint(
            MyDatagramProto, local_addr=('localhost', 1, 2, 3))
        self.assertRaises(
            AssertionError, self.loop.run_until_complete, coro)

    def test_create_datagram_endpoint_connect_err(self):
        self.loop.sock_connect = unittest.mock.Mock()
        self.loop.sock_connect.side_effect = OSError

        coro = self.loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, remote_addr=('127.0.0.1', 0))
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_datagram_endpoint_socket_err(self, m_socket):
        m_socket.getaddrinfo = socket.getaddrinfo
        m_socket.socket.side_effect = OSError

        coro = self.loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, family=socket.AF_INET)
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

        coro = self.loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, local_addr=('127.0.0.1', 0))
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)

    @unittest.skipUnless(IPV6_ENABLED, 'IPv6 not supported or enabled')
    def test_create_datagram_endpoint_no_matching_family(self):
        coro = self.loop.create_datagram_endpoint(
            asyncio.DatagramProtocol,
            remote_addr=('127.0.0.1', 0), local_addr=('::1', 0))
        self.assertRaises(
            ValueError, self.loop.run_until_complete, coro)

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_datagram_endpoint_setblk_err(self, m_socket):
        m_socket.socket.return_value.setblocking.side_effect = OSError

        coro = self.loop.create_datagram_endpoint(
            asyncio.DatagramProtocol, family=socket.AF_INET)
        self.assertRaises(
            OSError, self.loop.run_until_complete, coro)
        self.assertTrue(
            m_socket.socket.return_value.close.called)

    def test_create_datagram_endpoint_noaddr_nofamily(self):
        coro = self.loop.create_datagram_endpoint(
            asyncio.DatagramProtocol)
        self.assertRaises(ValueError, self.loop.run_until_complete, coro)

    @unittest.mock.patch('asyncio.base_events.socket')
    def test_create_datagram_endpoint_cant_bind(self, m_socket):
        class Err(OSError):
            pass

        m_socket.AF_INET6 = socket.AF_INET6
        m_socket.getaddrinfo = socket.getaddrinfo
        m_sock = m_socket.socket.return_value = unittest.mock.Mock()
        m_sock.bind.side_effect = Err

        fut = self.loop.create_datagram_endpoint(
            MyDatagramProto,
            local_addr=('127.0.0.1', 0), family=socket.AF_INET)
        self.assertRaises(Err, self.loop.run_until_complete, fut)
        self.assertTrue(m_sock.close.called)

    def test_accept_connection_retry(self):
        sock = unittest.mock.Mock()
        sock.accept.side_effect = BlockingIOError()

        self.loop._accept_connection(MyProto, sock)
        self.assertFalse(sock.close.called)

    @unittest.expectedFailure
    @unittest.mock.patch('asyncio.selector_events.logger')
    def test_accept_connection_exception(self, m_log):
        sock = unittest.mock.Mock()
        sock.fileno.return_value = 10
        sock.accept.side_effect = OSError(errno.EMFILE, 'Too many open files')
        self.loop.remove_reader = unittest.mock.Mock()
        self.loop.call_later = unittest.mock.Mock()

        self.loop._accept_connection(MyProto, sock)
        self.assertTrue(m_log.exception.called)  # FIXME
        self.assertFalse(sock.close.called)
        self.loop.remove_reader.assert_called_with(10)
        self.loop.call_later.assert_called_with(constants.ACCEPT_RETRY_DELAY,
                                                # self.loop._start_serving
                                                unittest.mock.ANY,
                                                MyProto, sock, None, None)


if __name__ == '__main__':
    unittest.main()
