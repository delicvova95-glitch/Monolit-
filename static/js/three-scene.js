import * as THREE from 'three';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';
import { RoomEnvironment } from 'three/addons/environments/RoomEnvironment.js';

export function initThreeScene() {
    const container = document.querySelector('#scene');
    const hero = document.querySelector('[data-hero]');
    const sticky = hero?.querySelector('.hero-sticky');
    if (!container || !hero || !sticky) return;

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(30, 1, .1, 100);
    camera.position.set(2.9, 2.35, 4.1);
    camera.lookAt(0, .22, 0);

    let renderer;
    try {
        renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    } catch {
        container.querySelector('[data-scene-loader]')?.remove();
        return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.6));
    renderer.setClearColor(0x000000, 0);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = .94;
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    container.appendChild(renderer.domElement);
    renderer.domElement.setAttribute('aria-hidden', 'true');

    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const environment = pmrem.fromScene(room, .04).texture;
    scene.environment = environment;
    room.dispose();
    pmrem.dispose();

    scene.add(new THREE.HemisphereLight(0xeeeade, 0x23282c, .45));
    const keyLight = new THREE.DirectionalLight(0xfff3de, 1.7);
    keyLight.position.set(-3.2, 5.2, 4);
    keyLight.castShadow = true;
    keyLight.shadow.mapSize.set(1024, 1024);
    keyLight.shadow.camera.near = 1;
    keyLight.shadow.camera.far = 15;
    keyLight.shadow.camera.left = -2.6;
    keyLight.shadow.camera.right = 2.6;
    keyLight.shadow.camera.top = 2.6;
    keyLight.shadow.camera.bottom = -2.6;
    keyLight.shadow.bias = -.0004;
    scene.add(keyLight);
    const edgeLight = new THREE.DirectionalLight(0xc2cfd6, .4);
    edgeLight.position.set(4.2, 2.2, -4.2);
    scene.add(edgeLight);
    const rimLight = new THREE.DirectionalLight(0xd9c6a2, .45);
    rimLight.position.set(1.2, 3.4, -5);
    scene.add(rimLight);

    const root = new THREE.Group();
    root.rotation.set(.1, -.5, -.05);
    root.scale.setScalar(1.3);
    scene.add(root);

    const shadowCatcher = new THREE.Mesh(
        new THREE.PlaneGeometry(6.5, 6.5),
        new THREE.ShadowMaterial({ opacity: .36 }),
    );
    shadowCatcher.rotation.x = -Math.PI / 2;
    shadowCatcher.position.y = -.06;
    shadowCatcher.receiveShadow = true;
    scene.add(shadowCatcher);

    let targetProgress = 0;
    let currentProgress = 0;
    let active = true;
    let frameId = 0;
    let lastTime = performance.now();

    function readScroll() {
        const distance = Math.max(1, hero.offsetHeight - window.innerHeight);
        targetProgress = THREE.MathUtils.clamp((window.scrollY - hero.offsetTop) / distance, 0, 1);
        sticky.style.setProperty('--hero-progress', targetProgress.toFixed(4));
        const copyOpacity = 1 - THREE.MathUtils.smoothstep(targetProgress, .1, .34);
        const revealOpacity = THREE.MathUtils.smoothstep(targetProgress, .66, .88);
        sticky.style.setProperty('--copy-opacity', copyOpacity.toFixed(3));
        sticky.style.setProperty('--copy-pointer', copyOpacity < .2 ? 'none' : 'auto');
        sticky.style.setProperty('--reveal-opacity', revealOpacity.toFixed(3));
        sticky.style.setProperty('--reveal-pointer', revealOpacity > .6 ? 'auto' : 'none');
    }

    function resize() {
        const { width, height } = container.getBoundingClientRect();
        if (!width || !height) return;
        renderer.setSize(width, height, false);
        camera.aspect = width / height;
        camera.updateProjectionMatrix();
    }

    function animate(time) {
        frameId = requestAnimationFrame(animate);
        if (!active || document.hidden) {
            lastTime = time;
            return;
        }
        const damping = 1 - Math.exp(-(time - lastTime) * .014);
        lastTime = time;
        currentProgress += (targetProgress - currentProgress) * damping;

        // Поворот плитки: короткий разворот от ракурса 3/4 и плавная остановка горизонтально, лицом к зрителю
        const turn = THREE.MathUtils.smoothstep(currentProgress, .04, .7);
        // Лёгкий дрейф после остановки, чтобы кадр оставался живым
        const settle = THREE.MathUtils.smoothstep(currentProgress, .7, 1);

        root.rotation.x = THREE.MathUtils.lerp(.1, .48, turn) + settle * .02;
        root.rotation.y = THREE.MathUtils.lerp(-.5, -.5 - Math.PI, turn);
        root.rotation.z = THREE.MathUtils.lerp(-.05, 0, turn);
        // При появлении текста плитка уступает место слева
        root.position.x = THREE.MathUtils.lerp(0, .62, THREE.MathUtils.smoothstep(currentProgress, .55, .9));
        root.position.y = THREE.MathUtils.lerp(0, .12, turn);
        camera.position.z = THREE.MathUtils.lerp(4.35, 4.7, turn);
        camera.lookAt(0, .22, 0);
        renderer.render(scene, camera);
    }

    const observer = new IntersectionObserver(entries => {
        active = entries[0].isIntersecting;
    }, { rootMargin: '100px' });
    observer.observe(hero);
    const resizeObserver = new ResizeObserver(resize);
    resizeObserver.observe(container);
    window.addEventListener('scroll', readScroll, { passive: true });
    renderer.domElement.addEventListener('webglcontextlost', event => {
        event.preventDefault();
        cancelAnimationFrame(frameId);
        container.classList.remove('is-ready');
    });
    resize();
    readScroll();
    animate(performance.now());

    new GLTFLoader().load(
        container.dataset.modelUrl || '/static/models/concrete-block-natural.glb?v=20261109-nomark',
        gltf => {
            const model = gltf.scene;
            const bounds = new THREE.Box3().setFromObject(model);
            const size = bounds.getSize(new THREE.Vector3());
            const center = bounds.getCenter(new THREE.Vector3());
            model.scale.set(2 / size.x, .6 / size.y, 1 / size.z);
            model.position.set(-center.x * model.scale.x, -bounds.min.y * model.scale.y, -center.z * model.scale.z);
            model.traverse(child => {
                if (!child.isMesh) return;
                child.material.color.set(0x858585);
                child.material.metalness = 0;
                child.material.roughness = 1;
                child.material.envMapIntensity = .3;
                child.castShadow = true;
            });
            root.add(model);
            container.classList.add('is-ready');
        },
        undefined,
        () => {
            container.querySelector('[data-scene-loader]')?.remove();
            cancelAnimationFrame(frameId);
        },
    );
}
