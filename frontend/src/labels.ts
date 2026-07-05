// dir_type → i18n role key(镜像后端 roles.py _ROLES;不在此表的 dir_type 无角色)
export const ROLE_KEYS: Record<string, string> = {
  text_encoders: "roles.textEncoder", clip: "roles.textEncoder", vae: "roles.vae",
  controlnet: "roles.controlnet", clip_vision: "roles.clipVision",
  upscale_models: "roles.upscale", embeddings: "roles.embedding",
  model_patches: "roles.modelPatch", style_models: "roles.styleModel",
  insightface: "roles.insightface", sams: "roles.sam", ultralytics: "roles.detection",
  facerestore_models: "roles.faceRestore", vae_approx: "roles.vaeApprox",
};
// 复刻后端 roles.label_for,但经 i18n 出显示串;t 由调用方(useI18n)传入
export function displayLabel(m: any, t: (k: string) => string): string {
  if (m.civitai_base) return m.civitai_base;
  if (m.base_arch && m.base_arch !== "unknown") return m.base_arch;
  const key = ROLE_KEYS[m.dir_type];
  return key ? t(key) : t("label.unknown");
}
export function isIdentified(m: any): boolean {
  return !!(m.civitai_found || (m.base_arch && m.base_arch !== "unknown") || ROLE_KEYS[m.dir_type]);
}
