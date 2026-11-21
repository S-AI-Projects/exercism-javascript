const DEFAULT_STUDENTS = [
  'Alice',
  'Bob',
  'Charlie',
  'David',
  'Eve',
  'Fred',
  'Ginny',
  'Harriet',
  'Ileana',
  'Joseph',
  'Kincaid',
  'Larry',
];

const PLANT_CODES = {
  G: 'grass',
  V: 'violets',
  R: 'radishes',
  C: 'clover',
};

// Alternative representation: keep the two rows and locate a student's window
// only when plants(student) is called, instead of building a plots object up
// front for every student.
export class Garden {
  constructor(diagram, students = DEFAULT_STUDENTS) {
    this.students = [...students].sort();
    this.rows = diagram.split('\n').map((row) => [...row]);
  }

  plants(student) {
    const firstCup = this.students.indexOf(student) * 2;
    return [
      this.rows[0][firstCup],
      this.rows[0][firstCup + 1],
      this.rows[1][firstCup],
      this.rows[1][firstCup + 1],
    ].map((plant) => PLANT_CODES[plant]);
  }
}
