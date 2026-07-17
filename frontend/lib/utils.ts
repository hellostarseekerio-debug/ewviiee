import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// Shared left-indent formula for rendering a folder tree's nesting depth
// (components/folders/folder-tree.tsx and folder-picker-dialog.tsx both
// render the same hierarchy, just in different layouts) - one constant
// pair instead of the same "8 + depth * 16" magic numbers duplicated in
// each file.
const FOLDER_INDENT_BASE_PX = 8;
const FOLDER_INDENT_STEP_PX = 16;

export function folderIndentPx(depth: number): number {
  return FOLDER_INDENT_BASE_PX + depth * FOLDER_INDENT_STEP_PX;
}
