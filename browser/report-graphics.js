import {
  Scene, Color, FogExp2, PerspectiveCamera, WebGLRenderer, GridHelper,
  AmbientLight, DirectionalLight, PointLight, MeshStandardMaterial,
  BoxGeometry, Mesh, Raycaster, Vector2, REVISION,
} from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// A plain object also permits the browser suite to inject isolated failures.
window.THREE = {
  Scene, Color, FogExp2, PerspectiveCamera, WebGLRenderer, GridHelper,
  AmbientLight, DirectionalLight, PointLight, MeshStandardMaterial,
  BoxGeometry, Mesh, Raycaster, Vector2, REVISION, OrbitControls,
};
