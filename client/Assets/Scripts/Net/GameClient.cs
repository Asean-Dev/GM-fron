using System;
using System.Collections.Concurrent;
using System.IO;
using System.Net.Sockets;
using System.Threading;
using Google.Protobuf;
using GM.Protocol;

namespace GM.Net
{
    /// <summary>
    /// TCP connection to the map server. Each frame is a 4-byte big-endian length followed by
    /// one protobuf message (see proto/game.proto). Messages are read on a background thread
    /// and handed to the main thread through <see cref="TryReceive"/>.
    /// </summary>
    public sealed class GameClient : IDisposable
    {
        // Must match MAX_FRAME_LEN in server/crates/protocol.
        const int MaxFrameLen = 64 * 1024;

        readonly TcpClient tcp;
        readonly NetworkStream stream;
        readonly ConcurrentQueue<ServerMsg> inbox = new ConcurrentQueue<ServerMsg>();
        readonly object sendLock = new object();
        volatile bool closed;

        public bool Connected => !closed;

        public GameClient(string host, int port)
        {
            tcp = new TcpClient { NoDelay = true };
            tcp.Connect(host, port);
            stream = tcp.GetStream();
            new Thread(ReadLoop) { IsBackground = true, Name = "GameClient.Read" }.Start();
        }

        public void Send(ClientMsg msg)
        {
            if (closed) return;
            var body = msg.ToByteArray();
            var frame = new byte[4 + body.Length];
            frame[0] = (byte)(body.Length >> 24);
            frame[1] = (byte)(body.Length >> 16);
            frame[2] = (byte)(body.Length >> 8);
            frame[3] = (byte)body.Length;
            Buffer.BlockCopy(body, 0, frame, 4, body.Length);
            try
            {
                lock (sendLock) stream.Write(frame, 0, frame.Length);
            }
            catch (Exception e) when (e is IOException || e is ObjectDisposedException)
            {
                closed = true;
            }
        }

        public bool TryReceive(out ServerMsg msg) => inbox.TryDequeue(out msg);

        void ReadLoop()
        {
            var header = new byte[4];
            try
            {
                while (!closed)
                {
                    ReadExactly(header);
                    int len = (header[0] << 24) | (header[1] << 16) | (header[2] << 8) | header[3];
                    if (len < 0 || len > MaxFrameLen) throw new IOException($"bad frame length {len}");
                    var body = new byte[len];
                    ReadExactly(body);
                    inbox.Enqueue(ServerMsg.Parser.ParseFrom(body));
                }
            }
            catch (Exception) when (closed)
            {
                // Dispose() closed the socket under us.
            }
            catch (Exception e)
            {
                UnityEngine.Debug.LogWarning($"Disconnected from map server: {e.Message}");
            }
            finally
            {
                closed = true;
            }
        }

        void ReadExactly(byte[] buf)
        {
            int read = 0;
            while (read < buf.Length)
            {
                int n = stream.Read(buf, read, buf.Length - read);
                if (n == 0) throw new IOException("server closed the connection");
                read += n;
            }
        }

        public void Dispose()
        {
            closed = true;
            tcp.Close();
        }
    }
}
