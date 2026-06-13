import * as THREE from "three";
import { POWER_COLORS } from "./config.js";

export class ToyEffects {
  constructor(scene) {
    this.scene = scene;
    this.particles = [];
    this.effects = [];
  }

  burst(position, color, count = 22, speed = 1.1, options = {}) {
    for (let i = 0; i < count; i += 1) {
      const mesh = new THREE.Mesh(
        options.geometry || new THREE.SphereGeometry(0.032 + Math.random() * 0.04, 10, 8),
        new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.9 })
      );
      mesh.position.copy(position);
      this.scene.add(mesh);
      this.particles.push({
        mesh,
        velocity: new THREE.Vector3((Math.random() - 0.5) * speed, Math.random() * speed * 1.1, (Math.random() - 0.5) * speed),
        born: performance.now(),
        life: options.life ?? 620 + Math.random() * 620,
        spin: Math.random() * 5,
      });
    }
  }

  hearts(position, color = 0xff8ca3, count = 9) {
    const geometry = heartGeometry();
    this.burst(position, color, count, 0.65, { geometry, life: 950 });
  }

  stars(position, color = 0xfff071, count = 12) {
    const geometry = new THREE.OctahedronGeometry(0.055);
    this.burst(position, color, count, 1.25, { geometry, life: 880 });
  }

  ring(position, color, maxScale = 1.6, lifeSeconds = 1.1, sphere = false) {
    const geometry = sphere ? new THREE.SphereGeometry(0.3, 32, 18) : new THREE.TorusGeometry(0.42, 0.018, 10, 72);
    const material = sphere
      ? new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.24, wireframe: true })
      : new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.72 });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.position.copy(position);
    if (!sphere) mesh.rotation.x = Math.PI / 2;
    this.scene.add(mesh);
    this.effects.push({ kind: "ring", mesh, born: performance.now(), life: lifeSeconds * 1000, maxScale });
  }

  projectile(start, end, color, onDone) {
    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(0.16, 18, 12),
      new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.95 })
    );
    mesh.position.copy(start);
    this.scene.add(mesh);
    this.effects.push({ kind: "projectile", mesh, start, end, born: performance.now(), life: 620, onDone });
  }

  powerSplash(powerName, position, count = 24) {
    const color = POWER_COLORS[powerName] || 0xffffff;
    if (powerName.includes("fire") || powerName.includes("ember")) this.stars(position, color, count);
    else if (powerName.includes("bubble") || powerName.includes("wave")) this.burst(position, color, count, 0.95, { life: 1000 });
    else this.burst(position, color, count, 1.2);
  }

  update(now, dt) {
    for (let i = this.particles.length - 1; i >= 0; i -= 1) {
      const particle = this.particles[i];
      const age = now - particle.born;
      if (age > particle.life) {
        this.scene.remove(particle.mesh);
        this.particles.splice(i, 1);
        continue;
      }
      particle.velocity.y -= 1.42 * dt;
      particle.mesh.position.addScaledVector(particle.velocity, dt);
      particle.mesh.rotation.z += particle.spin * dt;
      particle.mesh.material.opacity = 1 - age / particle.life;
    }

    for (let i = this.effects.length - 1; i >= 0; i -= 1) {
      const effect = this.effects[i];
      const age = now - effect.born;
      const t = Math.min(1, age / effect.life);
      if (effect.kind === "ring") {
        const scale = THREE.MathUtils.lerp(0.15, effect.maxScale, easeOutCubic(t));
        effect.mesh.scale.setScalar(scale);
        effect.mesh.material.opacity = (1 - t) * 0.72;
      }
      if (effect.kind === "projectile") {
        effect.mesh.position.lerpVectors(effect.start, effect.end, easeOutCubic(t));
        effect.mesh.scale.setScalar(1 + Math.sin(t * Math.PI) * 0.45);
      }
      if (age > effect.life) {
        this.scene.remove(effect.mesh);
        if (effect.onDone) effect.onDone();
        this.effects.splice(i, 1);
      }
    }
  }
}

function heartGeometry() {
  const shape = new THREE.Shape();
  shape.moveTo(0, 0.04);
  shape.bezierCurveTo(0, 0.08, -0.08, 0.1, -0.08, 0.02);
  shape.bezierCurveTo(-0.08, -0.04, -0.02, -0.08, 0, -0.12);
  shape.bezierCurveTo(0.02, -0.08, 0.08, -0.04, 0.08, 0.02);
  shape.bezierCurveTo(0.08, 0.1, 0, 0.08, 0, 0.04);
  return new THREE.ShapeGeometry(shape);
}

function easeOutCubic(t) {
  return 1 - Math.pow(1 - t, 3);
}

