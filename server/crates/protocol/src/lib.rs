//! Messages shared with the Unity client (generated from `proto/game.proto`) and the TCP framing.

use bytes::Bytes;
use tokio_util::codec::LengthDelimitedCodec;

pub mod pb {
    include!(concat!(env!("OUT_DIR"), "/gm.rs"));
}

pub use pb::{ClientMsg, ServerMsg, client_msg, server_msg};
pub use prost::Message;

/// Largest frame either side accepts. Guards against garbage length prefixes.
pub const MAX_FRAME_LEN: usize = 64 * 1024;

/// 4-byte big-endian length prefix, matching `GameClient.cs` on the Unity side.
pub fn codec() -> LengthDelimitedCodec {
    LengthDelimitedCodec::builder()
        .length_field_length(4)
        .big_endian()
        .max_frame_length(MAX_FRAME_LEN)
        .new_codec()
}

pub fn encode(msg: &impl Message) -> Bytes {
    Bytes::from(msg.encode_to_vec())
}

#[cfg(test)]
mod tests {
    use super::*;
    use bytes::BytesMut;
    use tokio_util::codec::{Decoder, Encoder};

    #[test]
    fn frame_roundtrip() {
        let msg = ClientMsg {
            msg: Some(client_msg::Msg::MoveTo(pb::MoveTo { x: 3, y: -4 })),
        };
        let mut buf = BytesMut::new();
        codec().encode(encode(&msg), &mut buf).unwrap();

        assert_eq!(&buf[..4], &(buf.len() as u32 - 4).to_be_bytes());

        let frame = codec().decode(&mut buf).unwrap().unwrap();
        assert_eq!(ClientMsg::decode(frame).unwrap(), msg);
    }
}
