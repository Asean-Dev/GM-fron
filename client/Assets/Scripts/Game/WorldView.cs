using System.Collections.Generic;
using GM.Net;
using GM.Protocol;
using UnityEngine;

namespace GM.Game
{
    /// <summary>
    /// Connects to the map server, mirrors every entity as a capsule, and turns a click or tap
    /// on the ground into a MoveTo request. Grid cell (x, y) maps to world position (x, 0, y).
    /// </summary>
    public sealed class WorldView : MonoBehaviour
    {
        [SerializeField] string host = "127.0.0.1";
        [SerializeField] int port = 7000;
        [SerializeField] string playerName = "player";
        [SerializeField] float smoothing = 12f;
        [SerializeField] Vector3 cameraOffset = new Vector3(0f, 14f, -10f);

        GameClient client;
        uint myId;
        Camera cam;
        readonly Dictionary<uint, Transform> entities = new Dictionary<uint, Transform>();
        readonly Dictionary<uint, Vector3> targets = new Dictionary<uint, Vector3>();

        // Lets the prototype run from any scene, including a new empty one: press Play.
        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        static void Bootstrap()
        {
            if (FindAnyObjectByType<WorldView>() == null)
                new GameObject(nameof(WorldView)).AddComponent<WorldView>();
        }

        void Start()
        {
            cam = Camera.main;
            if (cam == null)
            {
                cam = new GameObject("Main Camera").AddComponent<Camera>();
                cam.tag = "MainCamera";
            }
            if (FindAnyObjectByType<Light>() == null)
            {
                var sun = new GameObject("Sun").AddComponent<Light>();
                sun.type = LightType.Directional;
                sun.transform.rotation = Quaternion.Euler(50f, -30f, 0f);
            }

            try
            {
                client = new GameClient(host, port);
            }
            catch (System.Exception e)
            {
                Debug.LogError($"Cannot reach map server at {host}:{port}: {e.Message}");
                enabled = false;
                return;
            }
            client.Send(new ClientMsg { Hello = new Hello { Name = playerName } });
        }

        void Update()
        {
            while (client.TryReceive(out var msg)) Apply(msg);

            float t = 1f - Mathf.Exp(-smoothing * Time.deltaTime);
            foreach (var pair in entities)
                pair.Value.position = Vector3.Lerp(pair.Value.position, targets[pair.Key], t);

            // Touch input arrives as mouse button 0 on mobile.
            if (myId != 0 && Input.GetMouseButtonDown(0))
            {
                var ray = cam.ScreenPointToRay(Input.mousePosition);
                if (new Plane(Vector3.up, Vector3.zero).Raycast(ray, out float dist))
                {
                    var hit = ray.GetPoint(dist);
                    client.Send(new ClientMsg
                    {
                        MoveTo = new MoveTo { X = Mathf.RoundToInt(hit.x), Y = Mathf.RoundToInt(hit.z) }
                    });
                }
            }
        }

        void LateUpdate()
        {
            if (entities.TryGetValue(myId, out var me))
            {
                cam.transform.position = me.position + cameraOffset;
                cam.transform.LookAt(me.position);
            }
        }

        void OnDestroy() => client?.Dispose();

        void Apply(ServerMsg msg)
        {
            switch (msg.MsgCase)
            {
                case ServerMsg.MsgOneofCase.Welcome:
                    myId = msg.Welcome.EntityId;
                    BuildGround(msg.Welcome.MapWidth, msg.Welcome.MapHeight);
                    break;
                case ServerMsg.MsgOneofCase.Spawn:
                    Spawn(msg.Spawn);
                    break;
                case ServerMsg.MsgOneofCase.Move:
                    if (entities.ContainsKey(msg.Move.EntityId))
                        targets[msg.Move.EntityId] = CellToWorld(msg.Move.X, msg.Move.Y);
                    break;
                case ServerMsg.MsgOneofCase.Despawn:
                    if (entities.TryGetValue(msg.Despawn.EntityId, out var gone))
                    {
                        Destroy(gone.gameObject);
                        entities.Remove(msg.Despawn.EntityId);
                        targets.Remove(msg.Despawn.EntityId);
                    }
                    break;
            }
        }

        void Spawn(EntitySpawn s)
        {
            if (entities.ContainsKey(s.EntityId)) return;
            var go = GameObject.CreatePrimitive(PrimitiveType.Capsule);
            go.name = $"{s.Name} #{s.EntityId}";
            go.GetComponent<Renderer>().material.color = s.EntityId == myId ? new Color(0.3f, 0.8f, 0.4f) : Color.white;
            var pos = CellToWorld(s.X, s.Y);
            go.transform.position = pos;
            entities[s.EntityId] = go.transform;
            targets[s.EntityId] = pos;
        }

        static void BuildGround(uint width, uint height)
        {
            // Unity's plane is 10x10 units; cells are 1 unit, centred on whole numbers.
            var ground = GameObject.CreatePrimitive(PrimitiveType.Plane);
            ground.name = "Ground";
            ground.transform.localScale = new Vector3(width / 10f, 1f, height / 10f);
            ground.transform.position = new Vector3((width - 1) / 2f, 0f, (height - 1) / 2f);
            ground.GetComponent<Renderer>().material.color = new Color(0.45f, 0.7f, 0.35f);
        }

        // Capsules are 2 units tall with the pivot in the middle.
        static Vector3 CellToWorld(int x, int y) => new Vector3(x, 1f, y);
    }
}
