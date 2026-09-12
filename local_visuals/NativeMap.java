// SPDX-License-Identifier: GPL-3.0-only
import net.osmand.NativeJavaRendering;
import net.osmand.util.MapUtils;
import java.io.File;
import javax.imageio.ImageIO;
class NativeMap {
 public static void main(String[] a)throws Exception {
  var r=NativeJavaRendering.getDefault(null,null,System.getProperty("eotwb.fonts", "fonts"));
  if(r==null)throw new Exception("Native unavailable");
  try {
   String[] maps=a[0].split(java.util.regex.Pattern.quote(File.pathSeparator));
   if(maps.length>5)throw new Exception("Map count bound");
   for(String map:maps)if(!r.initMapFile(map,false))throw new Exception("Map unavailable");
   r.loadRuleStorage(null,"");
   int left=Integer.parseInt(a[2]),right=Integer.parseInt(a[3]),top=Integer.parseInt(a[4]),bottom=Integer.parseInt(a[5]),zoom=Integer.parseInt(a[6]);
   var c=new NativeJavaRendering.RenderingImageContext(left,right,top,bottom,zoom);
   if(c.width!=850||c.height!=700||zoom<6||zoom>17)throw new Exception("Viewport bounds");
   ImageIO.write(r.renderImage(c).getImage(),"png",new File(a[1]));
   System.out.println("BOUNDS\t"+c.sleft+"\t"+c.sright+"\t"+c.stop+"\t"+c.sbottom+"\t"+c.width+"\t"+c.height);
   double divisor=Math.pow(2,23-zoom);
   for(int i=7;i<a.length;i+=2)System.out.println("SAMPLE\t"+((MapUtils.get31TileNumberX(Double.parseDouble(a[i+1]))-left)/divisor)+"\t"+((MapUtils.get31TileNumberY(Double.parseDouble(a[i]))-top)/divisor));
  } finally {r.closeAllFiles();}
 }
}
