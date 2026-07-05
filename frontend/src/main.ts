import { createApp } from "vue";
import PrimeVue from "primevue/config";
import App from "./App.vue";
import { i18n } from "./i18n";
import "./style.css";
import "primeicons/primeicons.css";
// 注:主题 css 由 index.html 的 <link id="theme-link"> 承载,不在此静态 import
import Menu from "primevue/menu";
import Card from "primevue/card";
import Knob from "primevue/knob";
import ProgressBar from "primevue/progressbar";
import DataView from "primevue/dataview";
import Tree from "primevue/tree";
import Tag from "primevue/tag";
import Image from "primevue/image";
import Panel from "primevue/panel";
import InputSwitch from "primevue/inputswitch";
import Slider from "primevue/slider";
import InputNumber from "primevue/inputnumber";
import InputText from "primevue/inputtext";
import Button from "primevue/button";

const app = createApp(App).use(PrimeVue).use(i18n);
for (const [n, c] of Object.entries({ Menu, Card, Knob, ProgressBar, DataView, Tree,
  Tag, Image, Panel, InputSwitch, Slider, InputNumber, InputText, Button }))
  app.component(n, c as any);
app.mount("#app");
