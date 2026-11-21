import { pdfjs } from "react-pdf";
import workerSrc from "pdfjs-dist/build/pdf.worker.min.mjs?url";

import "react-pdf/dist/Page/TextLayer.css";
import "react-pdf/dist/Page/AnnotationLayer.css";

// pdf.js procesa el PDF en un Web Worker. Vite lo empaqueta y nos da su URL.
pdfjs.GlobalWorkerOptions.workerSrc = workerSrc;
