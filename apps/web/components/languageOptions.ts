// Define a type for each language option
interface LanguageOption {
    id: number;
    name: string;
    label: string;
    value: string;
  }
  
  // Define the languageOptions array with the appropriate type
  export const languageOptions: LanguageOption[] = [
    {
      id: 63,
      name: "JavaScript (Node.js 12.14.0)",
      label: "JavaScript(12.14)",
      value: "javascript",
    },
    {
      id: 50,
      name: "C (GCC 9.2.0)",
      label: "C(GCC 9.2)",
      value: "c",
    },
    {
      id: 54,
      name: "C++ (GCC 9.2.0)",
      label: "C++(GCC 9.2)",
      value: "cpp",
    },

    {
      id: 62,
      name: "Java (OpenJDK 13.0.1)",
      label: "Java13",
      value: "java",
    },

    {
      id: 71,
      name: "Python (3.8.1)",
      label: "Python3",
      value: "python",
    },

    {
      id: 82,
      name: "SQL (SQLite 3.27.2)",
      label: "SQL",
      value: "sql",
    }
  ];
  