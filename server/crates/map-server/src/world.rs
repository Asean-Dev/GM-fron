//! Map state and movement rules. Pure logic with no I/O, so it is unit-tested directly.

use std::collections::BTreeMap;

pub type EntityId = u32;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Cell {
    pub x: i32,
    pub y: i32,
}

#[derive(Debug)]
pub struct Entity {
    pub name: String,
    pub pos: Cell,
    target: Cell,
}

pub struct World {
    width: i32,
    height: i32,
    next_id: EntityId,
    entities: BTreeMap<EntityId, Entity>,
}

impl World {
    pub fn new(width: u32, height: u32) -> Self {
        assert!(width > 0 && height > 0, "map must not be empty");
        Self {
            width: width as i32,
            height: height as i32,
            // 0 means "no entity" on the client.
            next_id: 1,
            entities: BTreeMap::new(),
        }
    }

    pub fn size(&self) -> (u32, u32) {
        (self.width as u32, self.height as u32)
    }

    /// Spawns near the map centre, spread over a 7x7 patch so new players don't stack.
    pub fn spawn(&mut self, name: String) -> EntityId {
        let id = self.next_id;
        self.next_id += 1;
        let spread = id as i32;
        let pos = self.clamp(Cell {
            x: self.width / 2 + spread % 7 - 3,
            y: self.height / 2 + (spread / 7) % 7 - 3,
        });
        self.entities.insert(
            id,
            Entity {
                name,
                pos,
                target: pos,
            },
        );
        id
    }

    pub fn despawn(&mut self, id: EntityId) -> bool {
        self.entities.remove(&id).is_some()
    }

    pub fn get(&self, id: EntityId) -> Option<&Entity> {
        self.entities.get(&id)
    }

    pub fn entities(&self) -> impl Iterator<Item = (EntityId, &Entity)> {
        self.entities.iter().map(|(&id, e)| (id, e))
    }

    /// Targets outside the map are clamped to its edge.
    pub fn set_target(&mut self, id: EntityId, target: Cell) {
        let target = self.clamp(target);
        if let Some(e) = self.entities.get_mut(&id) {
            e.target = target;
        }
    }

    /// Advances one tick: every entity not at its target steps one cell toward it
    /// (8 directions, diagonals first). Returns the entities that moved.
    pub fn tick(&mut self) -> Vec<(EntityId, Cell)> {
        let mut moved = Vec::new();
        for (&id, e) in &mut self.entities {
            if e.pos == e.target {
                continue;
            }
            e.pos.x += (e.target.x - e.pos.x).signum();
            e.pos.y += (e.target.y - e.pos.y).signum();
            moved.push((id, e.pos));
        }
        moved
    }

    fn clamp(&self, c: Cell) -> Cell {
        Cell {
            x: c.x.clamp(0, self.width - 1),
            y: c.y.clamp(0, self.height - 1),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn world_with_player_at(pos: Cell) -> (World, EntityId) {
        let mut w = World::new(10, 10);
        let id = w.spawn("p".into());
        w.entities.get_mut(&id).unwrap().pos = pos;
        w.set_target(id, pos);
        (w, id)
    }

    #[test]
    fn walks_diagonally_then_straight() {
        let (mut w, id) = world_with_player_at(Cell { x: 0, y: 0 });
        w.set_target(id, Cell { x: 3, y: 1 });

        let path: Vec<Cell> = (0..3).map(|_| w.tick()[0].1).collect();
        assert_eq!(
            path,
            [
                Cell { x: 1, y: 1 },
                Cell { x: 2, y: 1 },
                Cell { x: 3, y: 1 }
            ]
        );
        assert!(w.tick().is_empty(), "arrived entities don't move");
    }

    #[test]
    fn targets_are_clamped_to_the_map() {
        let (mut w, id) = world_with_player_at(Cell { x: 8, y: 8 });
        w.set_target(id, Cell { x: 50, y: -5 });
        for _ in 0..20 {
            w.tick();
        }
        assert_eq!(w.get(id).unwrap().pos, Cell { x: 9, y: 0 });
    }

    #[test]
    fn spawns_inside_the_map_with_unique_ids() {
        let mut w = World::new(3, 3);
        let ids: Vec<_> = (0..60).map(|i| w.spawn(format!("p{i}"))).collect();
        assert_eq!(ids.len(), w.entities().count());
        for (_, e) in w.entities() {
            assert!((0..3).contains(&e.pos.x) && (0..3).contains(&e.pos.y));
        }
        assert!(w.despawn(ids[0]));
        assert!(!w.despawn(ids[0]));
    }
}
