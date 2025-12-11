# Diario-g26
Este es un proyecto para tener un diario anónimo moderado de forma descentralizada para la gen2026 del colegio san josé de cabrero 

## Nuevas Características

### Subida de Imágenes y Videos
- **Imágenes**: Puedes subir hasta 3 imágenes por entrada (JPG, PNG, WebP)
- **Videos**: Puedes subir 1 video por entrada (MP4, WebM)
- Los archivos se validan por tamaño (máx. 10MB para imágenes, 100MB para videos)
- Las imágenes se muestran en la vista previa y en las entradas publicadas
- Los videos incluyen un reproductor integrado con controles nativos

### Reproductor de Video
- Reproductor HTML5 con controles nativos
- Soporta pausa, reproducción y control de volumen
- Se muestra en las entradas con media incluidos

### Galería de Imágenes
- Haz clic en cualquier imagen para verla a tamaño completo en un modal
- Cierra el modal haciendo clic fuera, presionando ESC o el botón ×
- Las imágenes se cargan de forma perezosa (lazy loading) para mejor rendimiento

## Estructura de Archivos

- `uploads/` - Directorio donde se almacenan las imágenes y videos subidos (se crea automáticamente)
- El servidor crea las carpetas necesarias automáticamente
