import { editChangeSpan, marksPatch } from "../../src/contest_generator/static/js/fx/edit-patch.js";

for (const [a, b] of [
  ["ab(cd", "abcd"],
  ['ab"cd', "abcd"],
  ["ab#cd", "abcd"],
  ["ab\tcd", "abcd"],
  ["f() { x }", "f() {x }"],
]) {
  console.log(JSON.stringify(a), "->", JSON.stringify(b),
    JSON.stringify(editChangeSpan(a, b)));
}
