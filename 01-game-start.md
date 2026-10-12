In the first few minutes of the game, a sort of action packed tutorial is played.

1. You are travelling through hyperspace
2. You get a story message by Commander Crosshair, that the valuable cargo you are carying is being looked for by pirates and to be on your toes. (the message will be military sounding)
3. You are pulled out of hyperspace by the pirates.
4. You enter combat with the pirates, it's easy and you win in 30 seconds.
5. You jump to a station.
6. You dock and sell the valuable cargo.
7. You get money and upgrade the reactor and weapons of your ship.
8. You get shown a galaxy map and and told by the commander that you did a good job and that go find your destiny.
9. You get shown a list of quests to do.

This is a tutorial, after that mostly free play with quests will be present.

---
## Features required

## 2D

The game is 2D, all the time you see your ship in the middle vertically, left horizontally.
The visuals are not a grid, it's open space and a actual spaceship-shapes (but of couse ASCII) are shown. Colors are used freely to make it vibrant.

The event log is 1/3 of the screen.

### Hyperspace

When in hyperspace, characters are going around your ship to represent movement.
You cannot just jump to any system, you need to travel on predefined-routes between systems.
Each jump costs some fuel.

### Combat

Other ships are present in the 2D space. 
Each ship is marked A-Z and has subtargets (components) 01-99. The components of the ship for now are:
- reactor
- shield generator
- hyperdrive
- cargo hold

You enter commands to lock a target, optionally a subtarget. And command to start/stop firing. Weapons fire and aim automatically when fired. Weapons are lasers and show "tracers" on the screen travelling. Also hits are supposed to be show with explosions.

### Quest list

Command to get shown a list of quests avaialble, command to start a quest. A command to view details of active quests.

### Communcation

You can receive messages, like the one by the commander.
