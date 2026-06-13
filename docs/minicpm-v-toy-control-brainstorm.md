# MiniCPM-V Toy Control Brainstorm

Date: 2026-06-13

Working project: Tiny Toybox / Toy Room v2

Hackathon track: An Adventure in Thousand Token Wood

Source rules checked:

- Local copy: `hackathon-rules.md`
- Live page: https://huggingface.co/build-small-hackathon

## The North Star

Toy Room v2 should not feel like a big sandbox with a chat model attached.

It should feel like a tiny living world where the toys have eyes, preferences, little bodies, and enough agency to surprise the player.

The strongest version is:

> A tiny toy room where small AI toys look through their own eyes, understand what changed, and use physical powers to complete a small, visible ritual.

The hackathon wants delight, AI that is load-bearing, originality, and polish. That means the demo must make the AI's role obvious without a long explanation. The viewer should be able to see:

1. The toy saw something specific.
2. The toy chose a physical action because of what it saw.
3. The room changed visibly.
4. The toy reacted emotionally.
5. The world moved toward a clear end state.

If all five happen in the first 30-45 seconds, the demo becomes convincing.

## Current Problem With Toy Room v2

Toy Room v2 is technically rich, but the first impression can become noisy:

- four agents
- big room
- many objects
- many controls
- text brain, vision brain, trace policy, memories, audio, judge panel
- old/new model paths visible at the same time
- lots of proof, but not one obvious story

The issue is not lack of features. The issue is that the audience cannot immediately answer:

> What am I trying to do, and what did the AI do that a normal game script could not?

So the next step should not be "make the world larger." It should be "make the tiny world objective sharper."

## First-Principles Model Role

MiniCPM-V should not be the whole controller.

It should be the toy's visual cortex.

The best architecture is:

1. The renderer stays instant and deterministic.
2. Each toy has an agent-view camera.
3. After a meaningful event, MiniCPM-V receives the toy's camera frame.
4. MiniCPM-V returns compact perception:
   - what the toy sees
   - where attention should go
   - hazards
   - object affordances
   - emotional cue
   - optional blendshape cue
5. The action brain receives that perception plus compact room state.
6. The action brain emits bounded JSON.
7. The physics room executes the JSON through visible toy powers.
8. The UI shows a charming tiny thought bubble: "I see the tin can by the ramp."

In one line:

> MiniCPM-V sees. The action brain decides. The toy body performs.

That separation is important because it makes the demo reliable. Vision can be slower and sparse; touch, physics, movement, and powers stay immediate.

## What Would Feel Novel

The novel thing is not "a virtual pet with chat."

The novel thing is:

> A small-model toy council where each character has its own embodied visual perspective and its own physical powers.

This lets the app do things that a normal chatbot demo does not:

- Squeaky sees a falling block and freezes it.
- Electraica sees a shiny can and magnet-pulls it to the bin.
- Shark Girl sees a lonely object and bubble-lifts it to the group.
- Fire Boy gets dropped and the others rescue him.
- The pets can disagree because their cameras face different directions.
- A judge can see the pet-view frame and the action that followed it.

The most powerful proof is perspective:

> The agent did not receive an omniscient narration. It looked out from its little body.

## UI Principle

The player should mostly see the toy room, not the debug lab.

Keep the judge/evidence panels available, but the first screen should read like a finished toy:

- full-bleed room
- one clear objective
- pet-view thought bubble
- small progress strip
- active toy powers
- "Run tiny story" demo button

The brain trace should be cute and legible:

```text
Squeaky sees: soft ball near dominoes
Feeling: focused
Plan: freeze moving toy
Action: time_freeze -> all-moving
```

That is enough. The full JSON can live in a foldout/dev panel.

## Recommended Demo Objective

### Objective 1: Storytime Rescue

Pitch:

> Help the toys prepare the room for storytime. The AI toys must look around, clean up hazards, rescue each other, gather near the book, and celebrate.

Why this is probably the best end objective:

- It is instantly understandable.
- It is cute without needing lore.
- It gives the room a before/after state.
- It uses Toy Room v2's existing strongest systems: vision, recycling, rescue, memory, social play, generated object, powers.
- It makes the AI load-bearing: the toys must identify what is out of place from their own view.
- It creates a beautiful ending shot: all four toys gathered around the book/table with the room clean.

Demo beats:

1. The room opens messy: waste near the ramp, dominoes in danger, book off to the side, one toy unstable.
2. Squeaky looks through pet-view and says, "I see the dominoes wobbling."
3. Squeaky freezes or rewinds the danger.
4. Electraica sees the tin can and magnet-pulls it toward the recycle bin.
5. Fire Boy is dropped or tilted; Shark Girl comforts/rescues with bubble lift.
6. The player says, "Get ready for storytime."
7. The toy council gathers around the book/table.
8. One final toy wishes in a tiny lamp or piano.
9. End state: room glows, all toys face the book, one line from Squeaky: "The room is small enough to be safe now."

Minimum version:

- One main protagonist, Squeaky.
- One recyclable object.
- One hazard near dominoes.
- One gather-at-book ending.

Full version:

- All four agents take one turn each.
- Each turn uses their agent-view camera.
- Progress strip shows: See, Fix, Rescue, Gather, Celebrate.

Why MiniCPM-V matters:

- It identifies visible hazards and objects from camera frames.
- It gives each toy a different perspective.
- The action is not just button-triggered; it is visually grounded.

Risk:

- If the room is visually cluttered, vision feels random.

Mitigation:

- Make a special "Storytime Rescue" scene with fewer objects and stronger staging.

## Strong Alternative Objectives

### Objective 2: The Toy Council Mystery

Pitch:

> Something in the room changed while the toys were sleeping. Each toy looks from its own body and contributes one clue, then the council decides what to do.

Demo beats:

1. Player clicks "Start Mystery."
2. A new object appears or a tower is arranged.
3. Each toy scans from its own camera.
4. Squeaky sees the top object, Electraica sees the shiny object, Shark Girl sees the huddle, Fire Boy sees the ramp.
5. They vote on the answer: tower, parade, huddle, lost toy, or mess.
6. One toy acts physically on the answer.

Why it is novel:

- Multi-agent embodied perception is rare and memorable.
- The audience can understand "different eyes see different clues."

Why it may be risky:

- More dialogue can slow down the demo.
- Requires tight choreography to avoid confusion.

Best use:

- As a one-button sequence after the main objective, not the whole app.

### Objective 3: Protect The Domino Parade

Pitch:

> Squeaky is the tiny timekeeper. The player's job is to build a domino parade, then Squeaky must protect it from chaos using visual attention and time powers.

Demo beats:

1. Player arranges dominoes or clicks "Set parade."
2. A ball or cube rolls toward them.
3. MiniCPM-V sees the threat from Squeaky's view.
4. Squeaky freezes, rewinds, or bubbles the object.
5. If the dominoes survive, Squeaky celebrates.

Why it is strong:

- Very legible.
- Great for video.
- Squeaky has the clearest power identity.
- Smaller scope than four-agent v2.

Why it may be less novel:

- More like a clever game mechanic than a living world.

Best use:

- If the current v2 feels too busy, this should become the core polished demo.

### Objective 4: The Lost Moonberry

Pitch:

> A tiny moonberry is lost somewhere in the room. The toys must find it by looking through their own cameras and passing it to the story table.

Demo beats:

1. Moonberry spawns in a semi-random place.
2. Each toy scans from its own view.
3. One toy spots it and calls it out.
4. Another toy uses the right power to move it.
5. The berry reaches the table; storytime begins.

Why it is strong:

- Search-and-retrieve is easy to understand.
- Vision is truly load-bearing.
- Multi-agent camera perspectives matter.

Risk:

- If camera visibility is inconsistent, it may fail.

Mitigation:

- Use 3-4 curated spawn positions with clear sightlines.

### Objective 5: The Toy Room Doctor

Pitch:

> The toys act like tiny caretakers. They detect what is wrong in the room and heal it.

Possible problems:

- toy is tipped over
- recyclable waste is on the floor
- ball is stuck under table
- dominoes are falling
- lamp is off
- lonely toy is far from the group

Why it is strong:

- Emotional and practical.
- Very good fit for "AI improves lives" in miniature form.
- Lets each pet have a specialty.

Risk:

- If framed too generally, it becomes "AI helper" instead of strange toy.

Mitigation:

- Keep the language playful: not "assistant," but "room doctor," "tiny caretaker," "soft emergency."

### Objective 6: Wishcraft Toymaker

Pitch:

> The player asks for a tiny object, and the toy wishes it into the physics room, then the toys play with it.

Demo beats:

1. Player says, "I wish the room had a tiny piano."
2. The action model emits objectRecipe.
3. A physical toy piano appears from simple parts.
4. The pet-view camera sees it.
5. The toy council gathers around and reacts.

Why it is strong:

- Magical and surprising.
- Uses existing objectRecipe.
- Good "would show a friend" moment.

Why it is not enough alone:

- Vision is secondary unless the toy then sees and uses the wished object.

Best use:

- As the celebration beat in Storytime Rescue.

### Objective 7: Teach A Rule, Watch It Generalize

Pitch:

> Teach Squeaky a tiny law of the room, then watch it enforce the law later using vision and physics.

Example rule:

> "Dominoes are sacred. Never knock them."

Demo beats:

1. Player teaches the rule.
2. Squeaky stores memory.
3. A moving object threatens the dominoes.
4. Squeaky uses vision/state to recognize the situation.
5. Squeaky protects the dominoes.

Why it is strong:

- Shows memory.
- Shows AI load-bearing beyond one prompt.
- Already appears in the current judge demo.

Risk:

- Text-heavy if not staged visually.

Best use:

- First beat of Storytime Rescue or Protect The Domino Parade.

### Objective 8: Tiny Orchestra

Pitch:

> The pets inspect objects and turn the room into a little sound performance.

Demo beats:

1. MiniCPM-V sees objects: can, clock, book, lamp.
2. Each object becomes a small sound recipe.
3. Pets move objects into a pattern.
4. The room plays a short generated toy song.

Why it is beautiful:

- Audio adds delight.
- Fire Boy/Shark Girl/Electraica identities can become musical.

Risk:

- Harder to make the objective obvious.

Best use:

- End celebration after another objective.

### Objective 9: Physical Charades

Pitch:

> The player builds a shape from toys, and the pet guesses what it is from sight.

Demo beats:

1. Player stacks/lines/huddles objects.
2. Pet sees the arrangement.
3. Pet says, "You built a tiny tower" or "a domino parade."
4. Pet acts accordingly.

Why it is strong:

- Nice AI perception proof.
- Already partially implemented with arrangement detection.

Risk:

- If backend geometry detection does most of the work, MiniCPM-V feels less central.

Mitigation:

- Show the pet-view frame and ask MiniCPM-V for the explanation/label.

### Objective 10: Four-Pet Relay

Pitch:

> Move one special object across the room by chaining powers: freeze, lift, pull, nudge.

Demo beats:

1. Moon ball starts at one side.
2. Squeaky freezes hazards.
3. Electraica magnet-pulls metal bridge/object.
4. Shark Girl bubble-lifts the ball.
5. Fire Boy gives a final safe jump.
6. Object lands on the story table.

Why it is strong:

- Physical, visual, game-like.
- Clear progress.

Risk:

- More choreography and physics tuning.

Best use:

- If we want the app to feel more like a tiny game than a pet room.

### Objective 11: The Blindfold Challenge

Pitch:

> Turn off object JSON for one challenge and let the pet act from visual perception only.

Demo beats:

1. UI says "Pet-eye only."
2. Player moves an object.
3. MiniCPM-V describes the frame.
4. Action brain receives only the visual summary and coarse affordances.
5. Toy chooses a visible power.

Why it is excellent evidence:

- Very strong proof that MiniCPM-V matters.

Risk:

- Less reliable for a live demo.

Best use:

- As an optional badge/proof mode, not the default run.

### Objective 12: The Tiny Trial

Pitch:

> A crash happens. The toy council inspects the scene and decides who caused it, then repairs the room.

Why it is charming:

- Makes the toys feel social and theatrical.
- Good for social post copy.

Risk:

- Too much dialogue, not enough physical progress.

Best use:

- A field-notes/blog/video beat, not the core interaction.

## Ranking

Best core demo:

1. Storytime Rescue
2. Protect The Domino Parade
3. The Lost Moonberry

Best "AI load-bearing" proof:

1. The Blindfold Challenge
2. The Toy Council Mystery
3. Teach A Rule, Watch It Generalize

Best delight/social-post moment:

1. Wishcraft Toymaker
2. Tiny Orchestra
3. Physical Charades

Best realistic path from current v2:

1. Storytime Rescue
2. Teach A Rule, Watch It Generalize
3. Wishcraft Toymaker
4. Physical Charades
5. Recycling / Toy Room Doctor

## Recommended Product Shape

The app should open directly into one challenge:

> Help the toys get ready for storytime.

Visible progress:

```text
See -> Fix -> Rescue -> Gather -> Celebrate
```

The player can still poke, drag, throw, and chat, but the room has a purpose.

Suggested first-screen controls:

- Run Storytime Demo
- Reset Room
- Pet-eye / Room-eye toggle
- Active toy selector
- tiny power buttons
- minimal objective progress

Move these into a secondary "Evidence" panel:

- full JSON brain trace
- judge readiness
- training rows
- model endpoint details
- memory/debug logs

The video should show the pretty toy first and the evidence second.

## How MiniCPM-V Should Control And Interact

MiniCPM-V should produce a small perception packet, not arbitrary prose.

Example:

```json
{
  "summary": "A shiny can is near the ramp and the recycle bin is behind it.",
  "attention": "tin-can",
  "emotion": "focused",
  "blendshape": {
    "eye": 0.35,
    "brow": 0.2,
    "sparkle": 0.4
  },
  "hazards": ["can is on the walking path"],
  "toyObjects": ["tin-can", "recycle-bin", "cardboard-ramp"],
  "affordances": [
    {
      "objectId": "tin-can",
      "verb": "recycle",
      "confidence": 0.78
    }
  ]
}
```

Then the action brain turns that into:

```json
{
  "speech": "I see the shiny can. Tiny cleanup circuit engaged.",
  "emotion": "focused",
  "animation": "spark_spin",
  "interaction": {
    "verb": "recycle",
    "targetId": "tin-can"
  },
  "spell": {
    "spellName": "polite magnet",
    "ops": [
      {
        "op": "attract",
        "targetId": "tin-can",
        "radius": 3.2,
        "strength": 0.85,
        "color": "#66cbd8"
      }
    ]
  }
}
```

This makes the interaction legible:

- visual model noticed object
- action model chose behavior
- renderer moved object
- pet face and sound made it cute

## What To Change In The Current Build

### 1. Add a named challenge mode

Add `storytime_rescue` as a room mode.

It should stage fewer objects than the general v2 sandbox:

- book/table area
- one recyclable can
- one unstable block or ball
- domino line
- one lamp
- all four toys

### 2. Add an objective progress strip

Progress states:

- `saw_hazard`
- `protected_dominoes`
- `rescued_friend`
- `recycled_waste`
- `gathered_for_story`
- `celebrated`

### 3. Make pet-view explanations charming

Instead of showing raw "vision board" first, show one compact thought bubble:

```text
Squeaky sees: wobbling dominoes
Plan: freeze the noisy cube
```

### 4. Reduce first-screen debug density

Keep the readiness/evidence panel, but hide it behind "Evidence" or place it lower.

The first viewport should sell the toy, not the proof paperwork.

### 5. Make MiniCPM-V's output visible

Every vision-triggered action should visibly mark:

- camera source: `Squeaky's eyes`
- seen object: `tin-can`
- chosen affordance: `recycle`
- confidence or mood: optional

This makes the model contribution undeniable.

### 6. Use model names carefully

Do not make judges parse old/new model history.

Public copy should say:

> MiniCPM-V acts as the toys' visual cortex. A tiny action policy turns perception into bounded toy powers.

Developer panel can show exact endpoint/model.

### 7. Make the one-button demo a story, not a checklist

Current judge demo exercises many systems. Rename/reframe it:

> Run Storytime Rescue

Internally it can still hit the evidence checks, but externally it should feel like a small scene with a satisfying ending.

## Suggested 90-Second Demo Video

Opening shot:

> "This is a tiny toy room. Each toy sees from its own body."

Beat 1:

- Drag a ball near dominoes.
- Squeaky pet-view shows ball/dominoes.
- Squeaky freezes the moving ball.

Beat 2:

- Show Electraica's eyes.
- She spots the shiny can and recycles it.

Beat 3:

- Drop Fire Boy.
- Shark Girl or Squeaky comforts/rescues him.

Beat 4:

- Ask: "Get ready for storytime."
- Toys gather around book/table.

Beat 5:

- Wish in tiny piano or lamp.
- The room glows; toys celebrate.

Evidence flash:

- small model stack
- MiniCPM-V visual cortex
- action traces
- Gradio/HF Space

Closing line:

> "The AI is not answering questions. It is playing with the room."

## What Not To Do

- Do not lead with all four agents explaining themselves.
- Do not make the judge read a dense trace before seeing delight.
- Do not make the large room the point.
- Do not show older model confusion in the main UI.
- Do not depend on long free-form chat.
- Do not make MiniCPM-V responsible for realtime control loops.
- Do not add more objects until the objective is obvious.

## Decision

My recommendation:

> Make Storytime Rescue the public demo and keep Toy Room v2 as the underlying sandbox.

This preserves the technical work while giving it a small, emotionally clear shape.

The one-sentence product:

> Tiny Toybox is a Gradio-hosted AI toy room where MiniCPM-V gives each toy eyes, and the toys use small physical powers to rescue, clean, gather, and celebrate inside a tiny world.

The one-sentence judge proof:

> Without the AI vision/action loop, the toys cannot notice what changed, choose the right power, or complete the storytime ritual.

## Immediate Build Plan

1. Create a `storytime_rescue` scenario in Toy Room v2.
2. Add a progress strip: See, Fix, Rescue, Gather, Celebrate.
3. Rename the one-button judge demo to "Run Storytime Rescue."
4. Make each demo beat show a pet-view thought bubble.
5. Hide dense evidence behind a toggle.
6. Make the model copy say "MiniCPM-V visual cortex" and "tiny action brain."
7. Record the 90-second demo around that story.

